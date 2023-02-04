import datetime
import re
from typing import Any
from app.repositories import FileUserRepository, UserRepository
from app import models
from app.utils import now_dt


class UserContentService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo
        self._url_regex = r"((http|https):\/\/)?[a-zA-Z0-9.-]+(\.[a-zA-Z]{2,})"

    async def open_submit_modal(self, body, client, view_name: str) -> None:
        await client.views_open(
            trigger_id=body["trigger_id"],
            view=self._get_submit_modal_view(body, view_name),
        )

    async def open_pass_modal(self, body, client, view_name: str) -> None:
        res = await client.views_open(
            trigger_id=body["trigger_id"],
            view=self._get_loading_modal_view(body, view_name, "제출이력 확인 중"),
        )
        view_id = res["view"]["id"]
        await client.views_update(
            view_id=view_id, view=self._get_pass_modal_view(body, view_name, 2)
        )

    async def get_user(self, ack, body, view) -> models.User:
        user = self._user_repo.get(body["user"]["id"])
        if not user:
            await self.error_message(ack, "사용자가 등록되어 있지 않습니다.")
            raise ValueError
        if user.channel_id != view["private_metadata"]:
            await self.error_message(ack, "본인이 속한 채널이 아닙니다.")
            raise ValueError
        return user

    async def create_submit_content(
        self, ack, body, view, user: models.User
    ) -> models.Content:
        content_url = self._get_content_url(view)
        await self._validate_url(ack, content_url)
        content = models.Content(
            dt=datetime.datetime.strftime(now_dt(), "%Y-%m-%d %H:%M:%S"),
            user_id=body["user"]["id"],
            username=body["user"]["username"],
            content_url=content_url,
            category=self._get_category(view),
            description=self._get_description(view),
            tags=self._get_tag(view),
            type="submit",
        )
        user.contents.append(content)
        self._user_repo.update(user)
        return content

    async def create_pass_content(
        self, ack, body, view, user: models.User
    ) -> models.Content:
        await self._validate_pass(ack, body["user"]["id"])
        content = models.Content(
            dt=datetime.datetime.strftime(now_dt(), "%Y-%m-%d %H:%M:%S"),
            user_id=body["user"]["id"],
            username=body["user"]["username"],
            description=self._get_description(view),
            type="pass",
        )
        user.contents.append(content)
        self._user_repo.update(user)
        return content

    async def send_chat_message(
        self, client, logger, content: models.Content, channel_id
    ) -> None:
        description_chat_message = self._description_chat_message(content.description)
        if content.type == "submit":
            message = f"\n>>>🎉 *<@{content.user_id}>님 제출 완료.*{description_chat_message}\
                \ncategory : {content.category}{self._tag_chat_message(content.tags)}\
                \nlink : {content.content_url}"
        else:
            message = (
                f"\n>>>🙏🏼 *<@{content.user_id}>님 패스 완료.*{description_chat_message}"
            )

        try:
            await client.chat_postMessage(channel=channel_id, text=message)
        except Exception as e:
            logger.exception(f"Failed to post a message {str(e)}")

    async def error_message(self, ack, message: str = "") -> None:
        errors = {}
        errors["content"] = message
        await ack(response_action="errors", errors=errors)

    def _get_loading_modal_view(
        self, body, view_name: str, message: str
    ) -> dict[str, Any]:
        view = {
            "type": "modal",
            "private_metadata": body["channel_id"],
            "callback_id": view_name,
            "title": {"type": "plain_text", "text": "또봇"},
            "close": {"type": "plain_text", "text": "닫기"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚀💪🏼🍭 {message}...!",
                    },
                }
            ],
        }
        return view

    def _get_submit_modal_view(self, body, submit_view: str) -> dict[str, Any]:
        view = {
            "type": "modal",
            "private_metadata": body["channel_id"],
            "callback_id": submit_view,
            "title": {"type": "plain_text", "text": "또봇"},
            "submit": {"type": "plain_text", "text": "제출"},
            "blocks": [
                {
                    "type": "section",
                    "block_id": "required_section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "글 쓰느라 고생 많았어요~ 👏🏼👏🏼👏🏼\n[글 링크]와 [카테고리]를 제출하면 끝! 🥳",
                    },
                },
                {
                    "type": "input",
                    "block_id": "content",
                    "element": {
                        "type": "url_text_input",
                        "action_id": "url_text_input-action",
                    },
                    "label": {"type": "plain_text", "text": "글 링크", "emoji": True},
                },
                {
                    "type": "input",
                    "block_id": "category",
                    "label": {"type": "plain_text", "text": "카테고리", "emoji": True},
                    "element": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "카테고리 선택",
                            "emoji": True,
                        },
                        "options": [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "프로젝트",
                                    "emoji": True,
                                },
                                "value": "프로젝트",
                            },
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "기술 & 언어",
                                    "emoji": True,
                                },
                                "value": "기술 & 언어",
                            },
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "조직 & 문화",
                                    "emoji": True,
                                },
                                "value": "조직 & 문화",
                            },
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "취준 & 이직",
                                    "emoji": True,
                                },
                                "value": "취준 & 이직",
                            },
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "일상 & 생각",
                                    "emoji": True,
                                },
                                "value": "일상 & 생각",
                            },
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "기타",
                                    "emoji": True,
                                },
                                "value": "기타",
                            },
                        ],
                        "action_id": "static_select-action",
                    },
                },
                {"type": "divider"},
                {
                    "type": "input",
                    "block_id": "description",
                    "optional": True,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "plain_text_input-action",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "하고 싶은 말이 있다면 남겨주세요.",
                        },
                        "multiline": True,
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "하고 싶은 말",
                        "emoji": True,
                    },
                },
                {
                    "type": "input",
                    "block_id": "tag",
                    "label": {
                        "type": "plain_text",
                        "text": "태그",
                    },
                    "optional": True,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "dreamy_input",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "태그1,태그2,태그3, ... ",
                        },
                        "multiline": False,
                    },
                },
            ],
        }
        return view

    def _get_pass_modal_view(
        self, body, view_name: str, pass_count: int
    ) -> dict[str, Any]:
        view = {
            "type": "modal",
            "private_metadata": body["channel_id"],
            "callback_id": view_name,
            "title": {"type": "plain_text", "text": "또봇"},
            "submit": {"type": "plain_text", "text": "패스"},
            "blocks": [
                {
                    "type": "section",
                    "block_id": "required_section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"패스 하려면 아래 '패스' 버튼을 눌러주세요.\
                            \n현재 패스는 {pass_count}번 남았어요.\
                            \n패스는 연속으로 사용할 수 없어요.",
                    },
                },
                {
                    "type": "input",
                    "block_id": "description",
                    "optional": True,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "plain_text_input-action",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "하고 싶은 말이 있다면 남겨주세요.",
                        },
                        "multiline": True,
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "하고 싶은 말",
                        "emoji": True,
                    },
                },
            ],
        }
        return view

    def _get_description(self, view) -> str:
        description: str = view["state"]["values"]["description"][
            "plain_text_input-action"
        ]["value"]
        if not description:
            description = ""
        return description

    def _get_tag(self, view) -> str:
        tag = ""
        raw_tag: str = view["state"]["values"]["tag"]["dreamy_input"]["value"]
        if raw_tag:
            tag = ",".join(set(tag.strip() for tag in raw_tag.split(",") if tag))
        return tag

    def _get_category(self, view) -> str:
        category: str = view["state"]["values"]["category"]["static_select-action"][
            "selected_option"
        ]["value"]

        return category

    def _get_content_url(self, view) -> str:
        content_url: str = view["state"]["values"]["content"]["url_text_input-action"][
            "value"
        ]
        return content_url

    def _description_chat_message(self, description: str) -> str:
        description_message = ""
        if description:
            description_message = f"\n\n💬 '{description}'\n"
        return description_message

    def _tag_chat_message(self, tag: str | None) -> str:
        tag_message = ""
        if tag:
            tags = tag.split(",")
            tag_message = "\ntag : " + " ".join(set(f"`{tag.strip()}`" for tag in tags))
        return tag_message

    async def _validate_url(self, ack, content_url: str) -> None:
        if not re.match(self._url_regex, content_url):
            await self.error_message(ack, "링크는 url 주소여야 합니다.")

    async def _validate_pass(self, ack, user: models.User) -> None:
        if user.pass_count <= 0:
            await self.error_message(ack, "pass를 모두 소진하였습니다.")
            raise ValueError
        if user.before_type == "pass":
            await self.error_message(ack, "pass는 연속으로 사용할 수 없습니다.")
            raise ValueError


user_content_service = UserContentService(FileUserRepository())
