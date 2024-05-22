import math
import logging
from logging import getLogger

from langchain.docstore.document import Document
from langchain.chains.summarize import load_summarize_chain
from langchain.chat_models import AzureChatOpenAI
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
import tiktoken
from custom_handler import CustomCallbackHandler, LLMChangeHandler

GPT35 = 1
GPT4 = 2

CHUNK_SIZE = 4000
OVER_LAP = 200
MAX_TOKENS = 4000

SAME_MODEL_RETRIES = 5


class LangChainSummary:
    logger = getLogger()
    enc = tiktoken.get_encoding("cl100k_base")

    def __init__(self):
        self.model = None
        self.model_list = []

    def _split_document(self, text: str):
        enc = self.enc
        token_list = enc.encode(text)
        token_num = len(token_list)

        cutting_size = CHUNK_SIZE
        # 分割数の計算
        cutting_num = math.ceil(token_num / cutting_size)
        cutting_size = math.ceil((token_num+(cutting_num-1)*OVER_LAP)/(cutting_num))
        cutting_step = cutting_size - OVER_LAP if cutting_size > OVER_LAP else cutting_size
        all_token_list = [token_list[i: i+cutting_size] for i in range(0, token_num, cutting_step)]
        all_token_list = all_token_list[:-1] if all_token_list[:-1] else all_token_list
        #self.logger.info(f"all_token_list: {all_token_list}")
        text_list = [enc.decode(tokens) for tokens in all_token_list]
        docs = [Document(page_content=t) for t in text_list]

        return docs

    def set_model(self, deployment_name: str, api_type: str, api_base: str, api_version: str,
                  api_key: str, callback_handler=StreamingStdOutCallbackHandler):
        self.model = AzureChatOpenAI(
            client=None,
            deployment_name=deployment_name,
            openai_api_type=api_type,
            openai_api_base=api_base,
            openai_api_version=api_version,
            openai_api_key=api_key,
            temperature=0,
            max_tokens=MAX_TOKENS,
            streaming=True,
            max_retries=SAME_MODEL_RETRIES,
            callbacks=[callback_handler],
        )

    def make_summary(self, summary_trg: str, prompt_text: str,
                     callback_handler=None) -> str:

        if self.model is None:
            return "modelを設定してくだい"

        docs = self._split_document(summary_trg)

        # systemメッセージプロンプトテンプレートの準備
        system_message_prompt = SystemMessagePromptTemplate.from_template(prompt_text)
        # humanメッセージプロンプトテンプレートの準備
        human_template = "{text}"
        human_message_prompt = HumanMessagePromptTemplate.from_template(human_template, input_variables=["text"])

        system_map_prompt = SystemMessagePromptTemplate.from_template("与えられたテキストからフィラーなどの不必要な語句を削除し、短くしてください。")
        # map_promptの設定
        map_prompt = ChatPromptTemplate.from_messages([system_map_prompt, human_message_prompt])
        # chatプロンプトテンプレートの準備
        conbine_prompt = ChatPromptTemplate.from_messages([system_message_prompt, human_message_prompt])
        # プロンプトテンプレートによるチャットモデルの呼び出し

        self.logger.info(f"model is {self.model.openai_api_base}")
        chain = None
        chain = load_summarize_chain(self.model, chain_type="map_reduce",
                                        map_prompt=conbine_prompt,
                                        combine_prompt=conbine_prompt,
                                        collapse_prompt=conbine_prompt,
                                        verbose=True,
                                        token_max=10000)
        self.logger.info({"input_documents": docs})                  
        result = chain({"input_documents": docs}, return_only_outputs=True)

        if not result:
            self.logger.info('nothing result')

        return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=' %(levelname)s - %(message)s')
    # with open("/home/ec2-user/nagayama/resource/txt/1鈴木議員.txt", "r") as f:
    #     text = f.read()
    # text = text.replace("\n", "")
    text = '''あなたは中小企業の人事採用担当です。
来年度に入社予定の新卒社員向けに、ワークショップを開催予定です。
参加者は10人で、ビジネスマナーの基礎が分かる内容にしたいです。'''
    lc_summary = LangChainSummary()
    
    base_key_list = [
        ("https://ami-voxt-je.openai.azure.com/", "e3276cfc6b1d43159c570693e2b3c770"),
        ("https://ami-voxt-eu.openai.azure.com/", "16f8ffa32eff4553843c1d69c0713951"),
        ("https://ami-voxt-fc.openai.azure.com/", "915c2099a0e648489f01369582132d04"),
        ("https://ami-voxt-us.openai.azure.com/", "3099701b468e48148896b679628285a1")
    ]

    # モデルの登録
    for base, key in base_key_list[:1]:
        print(base)
        lc_summary.set_model(
            deployment_name="35t16k0613",
            api_type="azure",
            api_base=base,
            api_version="2023-03-15-preview",
            api_key=key,
            callback_handler=CustomCallbackHandler()
        )

        prompt_text = ('このワークショップで実施するべき内容を具体的に５つ考えてください。')
        res = lc_summary.make_summary(summary_trg=text, prompt_text=prompt_text,
                                      callback_handler=LLMChangeHandler())
        lc_summary.logger.info(res)
