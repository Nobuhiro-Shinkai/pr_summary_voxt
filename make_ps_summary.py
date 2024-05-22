import math
from typing import *
from logging import getLogger, basicConfig, INFO, DEBUG

import openai
import tiktoken

from simple_handler import SimpleHandler
logger = getLogger()

enc = tiktoken.get_encoding("cl100k_base")
MAX_TOKEN = 2000

class PartSplitSummary:

    logger = getLogger("pr_summary.summary")
    enc = tiktoken.get_encoding("cl100k_base")
    callback_hadler = None

    def __init__(self, callback_handler=SimpleHandler()):
        self.deployment_name = ""
        self.model_list = []
        self.callback_handler = callback_handler

    def _split_document(self, all_text: str, split_token_num=MAX_TOKEN*2, overlap=200):
        token_list = enc.encode(all_text)
        token_num = len(token_list)

        cutting_size = split_token_num - overlap

        # 分割数の計算
        cutting_num = math.ceil(token_num / cutting_size)
        cutting_size = math.ceil((token_num+(cutting_num-1)*overlap)/(cutting_num))
        self.logger.debug(f"length:{len(all_text)}, token_num:{token_num}, split_token_num:{split_token_num}, cutting_size: {cutting_size}, overlap:{overlap}, cutting_num:{cutting_num}")
        if token_num == cutting_size:
            overlap = 0
        self.logger.debug(f"cutting_size:{cutting_size}, token_num:{token_num}, overlap:{overlap} ")
        all_token_list = [token_list[i: i+cutting_size] for i in range(0, token_num, cutting_size-overlap)]
        if len(all_token_list) > 1:
            all_token_list = all_token_list[:-1]
        text_list = [enc.decode(tokens) for tokens in all_token_list]

        return text_list

    def set_model(self, deployment_name: str, api_type: str, api_base: str, api_version: str, api_key: str):

        try:
            self.deployment_name = deployment_name
            openai.api_type = api_type
            openai.api_base = api_base
            openai.api_version = api_version
            openai.api_key = api_key

        except KeyError as e:
            self.logger.error("パラメータが足りません。")
            raise e

    def _make_part_summary(self, summary_trg: str, prompt_text: str) -> str:
        '''
        GPTを実行する関数
        '''
        full_text = ""

        try:
            self.callback_handler.on_llm_start()
            response = openai.ChatCompletion.create(
                engine=self.deployment_name,
                messages=[
                    {
                        "role": "system",
                        "content": prompt_text,
                    },
                    {
                        "role": "user",
                        "content": summary_trg,
                    }
                ],
                temperature=0,
                max_tokens=MAX_TOKEN,
                top_p=0,
                frequency_penalty=0,
                presence_penalty=0,
                stop=None,
                timeout=10,
                stream=True
            )
            # 一トークンずつ出力
            for chunk in response:
                text = chunk['choices'][0]['delta'].get('content', '')
                full_text += text
                self.callback_handler.on_llm_new_token(text)

        except Exception as e:
            self.callback_handler.on_llm_error(e)
            raise e

        self.callback_handler.on_llm_end()

        return full_text

    def make_summary(self, summary_trg: str, prompt_text: str) -> str:
        
        prompt_token_num = len(enc.encode(prompt_text))

        # 五回分折りたたんでもダメな場合、終了する
        for _ in range(5):
            docs = self._split_document(summary_trg, split_token_num=(MAX_TOKEN*2-prompt_token_num))

            if len(docs) <= 1:
                self.callback_handler.is_last_generate()

            new_docs = []

            for idx, doc in enumerate(docs, start=1):
                self.callback_handler.show_progress(idx, len(docs))
                res_text = self._make_part_summary(doc, prompt_text)
                new_docs += [res_text]
            
            summary_trg = "\n".join(new_docs)

            if len(docs) <= 1:
                return summary_trg
            # 出力が収まるならいっかいまとめて出力
            elif 16000 > (prompt_token_num + len(enc.encode(summary_trg))):
                self.callback_handler.is_last_generate()
                res_text = self._make_part_summary(summary_trg, prompt_text)
                return res_text


if __name__ == "__main__":
    basicConfig(level=DEBUG, format=' %(levelname)s - %(message)s')

    with open("test.txt", "r") as f:
        text = f.read()
    text = text.replace("\n", "")

    ps_summary = PartSplitSummary()
    base_key_list = [
    ]

    # モデルの登録
    for base, key in base_key_list[:1]:

        ps_summary.set_model(
            deployment_name="35t16k0613",
            api_type="azure",
            api_base=base,
            api_version="2023-03-15-preview",
            api_key=key,
        )

    prompt_text = '''このテキストを要約してください。'''
    res = ps_summary.make_summary(summary_trg=text, prompt_text=prompt_text)
    ps_summary.logger.info(f"最終結果:\n{res}")
