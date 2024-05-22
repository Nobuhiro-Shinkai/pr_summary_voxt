from typing import *
from logging import getLogger


class SimpleHandler:
    logger = getLogger()
    tokens = ""

    def on_llm_start(self, **kwargs: Any) -> None:
        self.logger.info("要約開始\n")

    def on_llm_new_token(self, token, **kwargs: Any) -> None:
        '''新しいtokenが来たらprintする'''
        self.tokens += token

    def on_llm_end(self, **kwargs: Any) -> Any:
        """Run when LLM ends running."""
        self.logger.info("要約終了\n")

    def on_llm_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any) -> None:
        self.logger.info(f"llmエラー発生")
        self.logger.info(error)
    
    def is_last_generate(self, **kwargs: Any) -> Any:
        self.logger.info("最後の生成\n")

    def show_progress(self,idx: int, total_length: int, **kwargs: Any) -> Any:
        self.logger.info(f"現在の進捗 {idx}/{total_length}")
