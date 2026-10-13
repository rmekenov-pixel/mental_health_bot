import json
from collections.abc import Callable, Mapping
from typing import Any

from aiogram.exceptions import DataNotDictLikeError
from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, DefaultKeyBuilder, StateType, StorageKey
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import FsmState


class DatabaseStorage(BaseStorage):
    """Хранит FSM-состояния в той же БД, что и данные пользователя.

    MemoryStorage теряется при каждом рестарте/деплое, из-за чего начатый
    чек-ин или тест обрывался на середине.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession]):
        self._session_factory = session_factory
        self._key_builder = DefaultKeyBuilder(
            prefix="fsm",
            with_bot_id=True,
            with_destiny=True,
        )

    async def _get_row(
        self, session: AsyncSession, key: StorageKey
    ) -> FsmState | None:
        return await session.get(FsmState, self._key_builder.build(key))

    async def _write(self, key: StorageKey, **values: Any) -> None:
        async with self._session_factory() as session:
            row = await self._get_row(session, key)
            if row is None:
                session.add(FsmState(key=self._key_builder.build(key), **values))
            else:
                for field, value in values.items():
                    setattr(row, field, value)
            await session.commit()

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        await self._write(
            key,
            state=state.state if isinstance(state, State) else state,
        )

    async def get_state(self, key: StorageKey) -> str | None:
        async with self._session_factory() as session:
            row = await self._get_row(session, key)
            return row.state if row else None

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        if not isinstance(data, dict):
            raise DataNotDictLikeError(
                f"Data must be a dict or dict-like object, got {type(data).__name__}"
            )
        await self._write(
            key,
            data=json.dumps(data, ensure_ascii=False, default=str),
        )

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        async with self._session_factory() as session:
            row = await self._get_row(session, key)
            if not row or not row.data:
                return {}
            return json.loads(row.data)

    async def close(self) -> None:
        pass
