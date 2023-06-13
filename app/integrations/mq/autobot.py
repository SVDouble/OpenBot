import asyncio
import random
import signal

import pydantic

from app.integrations.mq.main import MqMessage
from app.integrations.mq.schemas import RedisMessage
from app.models import ContentType
from app.utils import get_logger, get_repository, get_settings

logger = get_logger(__file__)
settings = get_settings()
repo = get_repository()


class Client:
    def __init__(self, *, chat_id: int):
        self.chat_id = chat_id
        self._updates = asyncio.Queue()
        self.is_active = False

    async def receive_update(self, raw_message: dict):
        redis_message = RedisMessage(**raw_message)
        try:
            message = MqMessage.parse_raw(redis_message.data)
        except pydantic.ValidationError as e:
            logger.error(f"[Chat {self.chat_id}] Update Validation Error: {e}")
            return

        assert message.chat_id == self.chat_id
        if message.from_ == "bot":
            return

        await self._updates.put(message)

    async def generate_response(self, update: MqMessage) -> str:
        user = await repo.users.get(telegram_id=update.chat_id)
        if user is None:
            raise ValueError(f"User with telegram_id={update.chat_id} not found")
        if user.state is None:
            return "/start"
        state = await repo.states.get(user.state)
        question = await repo.questions.get(state.question_id)
        logger.info(f"[Chat {self.chat_id}] Question: {question}")
        actions = []
        if question.options:
            actions.append("select_option")
        if question.allow_arbitrary_input:
            actions.append("use_random_value")
        if question.allow_skip:
            actions.append("skip_question")
        if not actions:
            raise ValueError("No actions available")
        action = random.choice(actions)
        logger.info(f"[Chat {self.chat_id}] Action: {action}")
        match action:
            case "select_option":
                return random.choice(question.options).name
            case "use_random_value":
                match question.content_type:
                    case ContentType.TEXT:
                        return "F"
                    case ContentType.INTEGER:
                        return str(random.randint(0, 100))
                    case ContentType.FLOAT:
                        return "3.14"
            case "skip_question":
                return question.text_skip

    async def spawn(self):
        self.is_active = True
        while self.is_active:
            message = await self._updates.get()
            logger.info(f"[Chat {self.chat_id}] Received message: {message}")
            response = await self.generate_response(message)
            logger.info(f"[Chat {self.chat_id}] Sending response: {response}")
            await repo.db.publish(f"chat:{self.chat_id}", response)


async def main():
    pubsub = repo.db.pubsub()
    clients = [Client(chat_id=1)]
    subscriptions = {
        f"chat:{client.chat_id}": client.receive_update for client in clients
    }
    await pubsub.subscribe(**subscriptions)

    def _stop():
        for client in clients:
            client.is_active = False

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, _stop)
    loop.add_signal_handler(signal.SIGTERM, _stop)

    tasks = asyncio.TaskGroup()
    try:
        async with tasks:
            for client in clients:
                tasks.create_task(client.spawn())
            tasks.create_task(pubsub.run())
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe()
        await pubsub.close()


if __name__ == "__main__":
    asyncio.run(main())
