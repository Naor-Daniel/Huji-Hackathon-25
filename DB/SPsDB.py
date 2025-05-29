import consts
from typing import Optional
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

class SPsDB:
    def __init__(self):
        self.client = MongoClient(consts.URI, server_api=ServerApi('1'))

    def get_status(self):
        return self.client

    def get_sp(self, sp_id:str) -> :