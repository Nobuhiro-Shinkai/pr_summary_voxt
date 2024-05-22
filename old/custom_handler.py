from typing import *
from logging import getLogger

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import AgentAction, AgentFinish, LLMResult

class CustomCallbackHandler(BaseCallbackHandler):
    logger = getLogger()
    """Custom CallbackHandler."""
    tokens = ""
    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        self.logger.info("要約開始\n")

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        '''新しいtokenが来たらprintする'''
        self.tokens += token

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> Any:
        """Run when LLM ends running."""
        self.logger.info("要約終了\n")

    def on_llm_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        self.logger.info(f"llmエラー発生")
        self.logger.info(error)

        """Do nothing."""
        pass

    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        """Print out that we are entering a chain."""
        pass

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Print out that we finished a chain."""
        pass

    def on_chain_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        self.logger.info(f"chainエラー発生")
        self.logger.info(error)
        """Do nothing."""
        pass

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """Do nothing."""
        pass

    def on_tool_end(
        self,
        output: str,
        color: Optional[str] = None,
        observation_prefix: Optional[str] = None,
        llm_prefix: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """If not the final action, print out observation."""
        pass

    def on_tool_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """Do nothing."""
        pass

    def on_text(
        self,
        text: str,
        color: Optional[str] = None,
        end: str = "",
        **kwargs: Optional[str],
    ) -> None:
        """Run when agent ends."""
        pass

    def on_retry(self, error, **kwargs: Any):
        self.logger.info("on retry")
        self.logger.info(error)
        self.logger.info(kwargs)
        

class LLMChangeHandler:

    logger = getLogger()

    def on_llm_changed(
        self, pre_llm, crrent_llm, **kwargs: Any
    ) -> None:
        '''モデルを変えた際に呼ばれる関数'''
        self.logger.info((f"pre model base is {pre_llm.openai_api_base}"))
        self.logger.info(f"new model base is {crrent_llm.openai_api_base}")
