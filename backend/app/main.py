import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.config import get_settings
from app.database import create_indexes
from app.routes import animals, auth, reports, analysis, geospatial, demo, workflow, surveillance, media
from app.routes import assistant

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger('pashuraksha')


def create_app(database=None):
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app):
        client = None
        if database is None:
            client = MongoClient(settings.mongodb_uri, tz_aware=True, serverSelectionTimeoutMS=5000)
            try:
                client.admin.command('ping')
                app.state.db = client[settings.mongodb_database]
            except PyMongoError:
                logger.error('MongoDB unavailable; configure MONGODB_URI. No mock fallback is used.')
        if app.state.db is not None:
            create_indexes(app.state.db)
            # Warm the local classifier before accepting reports, avoiding a cold scientific-runtime import on the first submission.
            from app.triage.classifier import load_model
            load_model()
            if settings.demo_mode:
                from app.services.seed import seed_demo
                seed_demo(app.state.db)
        yield
        if client:
            client.close()

    app = FastAPI(title='PashuRaksha', version='0.1.0', description='Decision-support livestock surveillance. Identity and seed records are simulations.', lifespan=lifespan)
    app.state.db = database
    app.state.settings = settings
    app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(',')],
                       allow_credentials=False, allow_methods=['GET', 'POST', 'PUT'], allow_headers=['Authorization', 'Content-Type'])

    @app.exception_handler(PyMongoError)
    async def database_error(request: Request, error: PyMongoError):
        logger.error('Database operation failed: %s', type(error).__name__)
        return JSONResponse(status_code=503, content={'detail': 'Database temporarily unavailable. Please retry; your report ID prevents duplicates.'})

    @app.middleware('http')
    async def security_headers(request: Request, call_next):
        if request.headers.get('content-length', '').isdigit() and int(request.headers['content-length']) > 10 * 1024 * 1024:
            return JSONResponse(status_code=413, content={'detail': 'Request exceeds the 10 MB upload envelope.'})
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/api/health')
    def health():
        available = app.state.db is not None
        if available and database is None:
            try:
                app.state.db.command('ping')
            except PyMongoError:
                available = False
        result = {'status': 'ok' if available else 'unavailable',
                  'database': 'test-injected' if database is not None else ('mongodb' if available else 'unavailable'),
                  'demo_mode': settings.demo_mode}
        return JSONResponse(status_code=200 if available else 503, content=result)

    app.include_router(auth.router, prefix='/api')
    app.include_router(animals.router, prefix='/api')
    app.include_router(geospatial.router, prefix='/api')
    app.include_router(reports.router, prefix='/api')
    app.include_router(analysis.router, prefix='/api')
    app.include_router(demo.router, prefix='/api')
    app.include_router(workflow.router, prefix='/api')
    app.include_router(surveillance.router, prefix='/api')
    app.include_router(media.router, prefix='/api')
    app.include_router(assistant.router, prefix='/api')
    return app


app = create_app()
