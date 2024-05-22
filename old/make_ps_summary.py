import math
from typing import *
from logging import getLogger, basicConfig, INFO

import openai
import tiktoken

from simple_handler import SimpleHandler
logger = getLogger()

openai.api_type = "azure"
openai.api_base = "https://atd-nlp-test1-1.openai.azure.com/"
openai.api_version = "2023-03-15-preview"
openai.api_key = "49d9ff2cb5bd48ca80ce8704e5246f76"

enc = tiktoken.get_encoding("cl100k_base")
MAX_TOKEN = 2000

class PartSplitSummary:

    logger = getLogger()
    enc = tiktoken.get_encoding("cl100k_base")
    callback_hadler = None

    def __init__(self, callback_handler=SimpleHandler()):
        self.deployment_name = ""
        self.model_list = []
        self.callback_handler = callback_handler

    def _split_document(self, all_text: str, split_token_num=4000, overlap=200):
        token_list = enc.encode(all_text)
        token_num = len(token_list)

        cutting_size = split_token_num

        # 分割数の計算
        cutting_num = math.ceil(token_num / cutting_size)
        cutting_size = math.ceil((token_num+(cutting_num-1)*overlap)/(cutting_num))
        all_token_list = [token_list[i: i+cutting_size] for i in range(0, token_num, cutting_size-overlap)]
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
            docs = self._split_document(summary_trg)

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
            elif 16000 > MAX_TOKEN + prompt_token_num + len(enc.encode(summary_trg)):
                self.callback_handler.is_last_generate()
                res_text = self._make_part_summary(summary_trg, prompt_text)
                return res_text


if __name__ == "__main__":
    basicConfig(level=INFO, format=' %(levelname)s - %(message)s')

    with open("/home/ec2-user/nagayama/resource/gptSample/sum_trg.txt", "r") as f:
        text = f.read()
    text = text.replace("\n", "")

    ps_summary = PartSplitSummary()
    base_key_list = [
        ("https://ami-voxt-je.openai.azure.com/", "e3276cfc6b1d43159c570693e2b3c770"),
        ("https://ami-voxt-eu.openai.azure.com/", "16f8ffa32eff4553843c1d69c0713951"),
        ("https://ami-voxt-fc.openai.azure.com/", "915c2099a0e648489f01369582132d04"),
        ("https://ami-voxt-us.openai.azure.com/", "3099701b468e48148896b679628285a1")
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

    prompt_text = '''
与えられたテキストを以下の項目に分けてそれぞれ箇条書きで要約してください。
(1)本日のプロダクトミーティング
(2)ScribeAssistを使用して議事録作成した感想
(3)全体スケジュール
(4)問合せ状況
(5)サービスの利用状況
(6)営業フィードバック
(7)開発進捗報告
(8)次回のプロダクトミーティング
'''
    res = ps_summary.make_summary(summary_trg=text, prompt_text=prompt_text)
    ps_summary.logger.info(f"最終結果:\n{res}")
