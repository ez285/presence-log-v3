from __future__ import annotations
from typing import TYPE_CHECKING, Sequence, Any
if TYPE_CHECKING:
    from sqlalchemy import CursorResult, Engine

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, Row
from sqlalchemy.exc import SQLAlchemyError
import streamlit as st

load_dotenv(os.path.join(os.path.dirname(__file__), 'config.env'))

def get_value_type(value:tuple|int|float|str|bool) -> tuple[str, int|float|str|bool]:
    if isinstance(value, tuple) and value[0] == 'entity_ref':
        return 'entity_ref', value[1]
    elif isinstance(value, bool):
        return 'boolean', value
    elif isinstance(value, int):
        return 'integer', value
    elif isinstance(value, float):
        return 'float', value
    elif isinstance(value, str):
        return 'text', value
    else:
        raise ValueError('Wrong given type')

class Database:
    _engine = None
    @classmethod
    def _get_engine(cls) -> Engine:
        if cls._engine is None:
            DB_USER = st.secrets.Database['DB_USER']
            DB_PASSWORD = st.secrets.Database['DB_PASSWORD']
            DB_HOST = st.secrets.Database['DB_HOST']
            DB_PORT = st.secrets.Database['DB_PORT']
            DB_NAME = st.secrets.Database['DB_NAME']
            DB_URL = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
            cls._engine = create_engine(DB_URL, pool_size=5, max_overflow=10, pool_recycle=3600)
        return cls._engine

    def __init__(self) -> None:
        self.Engine = self._get_engine()
    
    def query(self, sql, params=None) -> Sequence[Row[Any]]:
        with self.Engine.connect() as conn:
            res = conn.execute(text(sql), params or {})
            return res.fetchall() if res.returns_rows else []

    def execute(self, sql, params=None) -> Sequence[Row[Any]]:
        with self.Engine.connect() as conn:
            try:
                res = conn.execute(text(sql), params or {})
                conn.commit()
                return res.fetchall() if res.returns_rows else []
            except SQLAlchemyError as e:
                conn.rollback()
                raise
    
    def insert_entity(self, entity_type:str) -> int:
        sql = 'INSERT INTO entities (entity_type) VALUES (:entity_type) RETURNING entity_id'
        params = {'entity_type': entity_type}
        return self.execute(sql, params)[0].entity_id
    
    def insert_entity_properties(self, entity_id:int, properties:dict) -> list[int]:
        ids = []
        for property_name, property_value_mix in properties.items():
            sql = ('INSERT INTO properties (entity_id, property_name, property_value, value_type) '
                   'VALUES (:entity_id, :property_name, :property_value, :value_type) '
                   'RETURNING property_id') 
            value_type, property_value = get_value_type(property_value_mix)
            params = {'entity_id': entity_id, 'property_name': property_name, 'property_value': str(property_value), 'value_type': value_type}
            ids.append(self.execute(sql, params)[0].property_id)
        return ids
