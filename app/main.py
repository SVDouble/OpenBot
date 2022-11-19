import asyncio

import ruamel.yaml

from app.engine import Engine
from app.schemas import StateChart
from app.settings import get_settings
from app.utils import get_logger

logger = get_logger(__file__)
settings = get_settings()


async def main():
    path = settings.project_root / "static" / "flip-flop.yaml"
    with open(path) as f:
        data = ruamel.yaml.YAML(typ="safe", pure=True).load(f)
    statechart = StateChart.parse_obj(data)
    engine = Engine(statechart)
    await engine.run()


if __name__ == "__main__":
    asyncio.run(main())
