"""Explicit operator provisioning for professional roles; no public role elevation."""
import argparse
import getpass
from pymongo import MongoClient
from app.auth import password_hasher
from app.config import get_settings
from app.database import create_indexes, new_id, utcnow
from app.schemas import Register


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email',required=True)
    parser.add_argument('--name',required=True)
    parser.add_argument('--district',required=True)
    parser.add_argument('--role',required=True,choices=['farmer','paravet','vet','lab','admin'])
    args=parser.parse_args()
    password=getpass.getpass('Private password (10+ characters): ')
    if password!=getpass.getpass('Confirm password: '):
        raise SystemExit('Passwords do not match; no account created.')
    data=Register(email=args.email,name=args.name,district=args.district,password=password)
    settings=get_settings()
    with MongoClient(settings.mongodb_uri,tz_aware=True,serverSelectionTimeoutMS=5000) as client:
        db=client[settings.mongodb_database];create_indexes(db)
        email=str(data.email).lower()
        if db.users.find_one({'email':email}):
            raise SystemExit('Account already exists; no roles or credentials were changed.')
        db.users.insert_one({'_id':new_id(),'name':data.name,'email':email,'district':data.district,
            'role':args.role,'password_hash':password_hasher.hash(data.password),'created_at':utcnow()})
    print('Account created. Professional verification remains the deploying organization’s responsibility.')


if __name__=='__main__':main()
