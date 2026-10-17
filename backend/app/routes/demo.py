from fastapi import APIRouter, Depends, Request
from pydantic import Field

from app.auth import get_db, roles
from app.schemas import StrictModel
from app.services import demo

router = APIRouter(prefix='/demo', tags=['Labelled synthetic demo'])


class ReplayInput(StrictModel):
    steps: int = Field(default=1, ge=1, le=11)


@router.get('/status')
def status(request: Request, user=Depends(roles('admin')), db=Depends(get_db)):
    return demo.status(db, user, request.app.state.settings)


@router.post('/replay')
def replay(payload: ReplayInput, request: Request, user=Depends(roles('admin')), db=Depends(get_db)):
    return demo.replay(db, user, request.app.state.settings, payload.steps)
