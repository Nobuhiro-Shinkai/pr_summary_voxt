from pprint import pprint
from logging import getLogger

import openai
from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain.chains.mapreduce import MapReduceChain
from langchain.docstore.document import Document
from langchain.chains.summarize import load_summarize_chain
from langchain.chat_models import AzureChatOpenAI
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.prompts.chat import (
	ChatPromptTemplate,
	SystemMessagePromptTemplate,
	HumanMessagePromptTemplate,
)

from custom_handler import CustomCallbackHandler
import requests
import uuid
import logging

GPT35 = 1
GPT4 = 2

CHUNK_SIZE = 2000
OVER_LAP = 200

logger_ = logging.getLogger("pr_summary.langchain")

class LangChainSummary:

	def __init__(self):
		self.model = None
		#self.deployment_name = "gpt-35-turbo" if gpt_mode == 1 else "gpt-4"

	def _split_document(self, text: str):
		text_splitter = RecursiveCharacterTextSplitter(
				chunk_size=CHUNK_SIZE,
				chunk_overlap=OVER_LAP,
				length_function=len,
		)
		texts = text_splitter.split_text(text)
		docs = [Document(page_content=t) for t in texts]

		return docs

	def set_model(self, api_type: str, api_base: str, api_version: str,
				  api_key: str, callback_handler=StreamingStdOutCallbackHandler):
		self.callbacks = callback_handler
		"""self.model = AzureChatOpenAI(
			client=None,
			deployment_name=self.deployment_name,
			openai_api_type=api_type,
			openai_api_base=api_base,
			openai_api_version=api_version,
			openai_api_key=api_key,
			temperature=0,
			max_tokens=4000-CHUNK_SIZE,
			streaming=True,
			callbacks=[callback_handler],
		)"""


	def make_summary(self, summary_trg: str, prompt_text: str) -> str:

		#if self.model is None:
		#	return "modelを設定してくだい"

		docs = self._split_document(summary_trg)
		#logger_.debug(summary_trg)
		#logger_.debug(docs)

		# systemメッセージプロンプトテンプレートの準備
		system_message_prompt = SystemMessagePromptTemplate.from_template(prompt_text)
		# humanメッセージプロンプトテンプレートの準備
		human_template = "{text}"
		human_message_prompt = HumanMessagePromptTemplate.from_template(human_template, input_variables=["text"])
		# chatプロンプトテンプレートの準備
		chat_prompt = ChatPromptTemplate.from_messages([system_message_prompt, human_message_prompt])
		# プロンプトテンプレートによるチャットモデルの呼び出し

		#chain = load_summarize_chain(self.model, chain_type="map_reduce",
		#							 map_prompt=chat_prompt, combine_prompt=chat_prompt)
		#result = chain({"input_documents": docs}, return_only_outputs=True)
		#count += len(self.encoding.encode(result))

		requestId = str(uuid.uuid4())

		payload = {'prompt': 'human_message_prompt', 'text': summary_trg, 'requestId':requestId}
		logger_.debug(f"payload: {payload}")
		requests.post("https://nlp-textpickup-dev.amivoice.com/summary_test/summary/", data=payload)
		logger_.debug("requests.post done")

		while True:
			payload = {'requestId':requestId}
			r = requests.post("https://nlp-textpickup-dev.amivoice.com/summary_test/getprogress/", data=payload)
			res = r.json()
			logger_.debug(f"requests.post result:{res}")
			if res['result']:
				if res['event'] == 'llm_start': 
					self.callbacks.on_llm_start(None, [res['token']])
				elif res['event'] == 'llm_new_token': 
					self.callbacks.on_llm_new_token(res['token'])
				elif res['event'] == 'llm_end': 
					self.callbacks.on_llm_end(None)
					break

		return ""


if __name__ == "__main__":

	with open("/home/s-nagayama/gptSample/gpt3/resource/productMTG/2023_0301/書き起こし/全文.txt", "r") as f:
		text = f.read()
	text = text.replace("\n", "")

	lc_summary = LangChainSummary(GPT4)

	# パラメータの設定
	lc_summary.set_model(
		api_type="azure",
		api_base="https://atd-nlp-test1-1.openai.azure.com/",
		api_version="2023-03-15-preview",
		api_key="49d9ff2cb5bd48ca80ce8704e5246f76",
		callback_handler=CustomCallbackHandler()
	)

	res = lc_summary.make_summary(summary_trg=text, prompt_text="このテキストを要約してください。")
	# print(res)
