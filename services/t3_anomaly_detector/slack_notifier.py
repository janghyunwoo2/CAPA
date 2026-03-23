import os
import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)

class SlackNotifier:
    def __init__(self, token, channel_id, enabled=True):
        self.enabled = enabled
        if not enabled or not token or not channel_id:
            self.client = None
            self.enabled = False
            return
            
        self.client = WebClient(token=token)
        self.channel_id = channel_id

    def send_message(self, text):
        if not self.enabled:
            return None
            
        try:
            response = self.client.chat_postMessage(
                channel=self.channel_id,
                text=text
            )
            return response
        except SlackApiError as e:
            logger.error(f"Slack 메시지 전송 실패: {e.response['error']}")
            return None

    def send_file(self, file_path, title, initial_comment=None):
        if not self.enabled or not os.path.exists(file_path):
            return None
            
        try:
            # files_upload_v2 사용 추천
            response = self.client.files_upload_v2(
                channel=self.channel_id,
                file=file_path,
                title=title,
                initial_comment=initial_comment
            )
            return response
        except SlackApiError as e:
            logger.error(f"Slack 파일 전송 실패: {e.response['error']}")
            return None
