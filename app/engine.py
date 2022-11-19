import asyncio
import datetime

from sismic.interpreter import Interpreter
from sismic.io.datadict import import_from_dict

from app.schemas import StateChart
from app.settings import get_settings
from app.utils import get_logger

logger = get_logger(__file__)
settings = get_settings()


class Engine:
    def __init__(self, statechart: StateChart):
        self.statechart: StateChart = statechart
        self.interpreter: Interpreter
        self._last_activity_time = datetime.datetime.now()
        self._is_active = False

    async def _run_clock(self, interval: float = 0.25):
        self.interpreter.clock.start()

        while self._is_active:
            now = datetime.datetime.now()
            if now - self._last_activity_time > datetime.timedelta(seconds=interval):
                await self._dispatch_event("clock")
            await asyncio.sleep(interval)

        self.interpreter.clock.stop()

    async def _dispatch_event(self, event: str):
        self.interpreter.queue(event)
        self.interpreter.execute(max_steps=42)
        self._last_activity_time = datetime.datetime.now()

    async def _initialize(self):
        self._is_active = True

        # create the interpreter
        statechart = import_from_dict(
            dict(statechart=self.statechart.dict(by_alias=True))
        )
        statechart.validate()
        self.interpreter: Interpreter = Interpreter(statechart, ignore_contract=True)

        # initialize the fsm
        await self._dispatch_event("init")

    async def run(self):
        logger.info("starting the engine")
        await self._initialize()
        await self._run_clock()

    async def stop(self):
        logger.info(f"stopping the engine'")
        self._is_active = False
