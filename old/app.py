import os
import sys

from flask import Flask, request, redirect, url_for, render_template, make_response, jsonify, session
from flask_httpauth import HTTPBasicAuth
import logging.config
from pathlib import Path
baseDir = Path(__file__).parent

import json
import pprint
import threading
import time
from queue import Queue
import openai
import random
#from make_summary_langchain import LangChainSummary, GPT35, GPT4
from make_ps_summary import PartSplitSummary
from simple_handler import SimpleHandler
from make_summary_langchain_test import LangChainSummary as LangChainSummaryTest
from typing import *
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import LLMResult
from tokenmodel import TokenModel
import tiktoken
import datetime
#from custom_handler import CustomCallbackHandler
from rr_model import RoundRobinModel


UPLOAD_FOLDER = baseDir / 'prompt'
RESULT_FOLDER = baseDir / 'result'
DEBUG_FOLDER = baseDir / 'debug'

REGEX_LIST = baseDir / 'regex_list.txt'

application = Flask(__name__)
application.config.from_envvar('PRSUMMARY_CONFIG_FILE')
logging.config.fileConfig(baseDir / 'logging.conf', disable_existing_loggers=False)
logger_ = logging.getLogger("pr_summary")

#application.config['TEST_MODE'] = False
#application.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
#application.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
#auth = HTTPBasicAuth()

logger_.debug("baseDir:{}".format(baseDir))
for key in os.environ:
	val = os.environ[key]
	logger_.debug('env {}: {}'.format(key, val))
for key in application.config:
	val = application.config[key]
	logger_.debug('config {}: {}'.format(key, val))
	
#@auth.get_password
def get_pw(username):
	ids = application.config['USER_ID'].split(",")
	passes = application.config['PASSWORD'].split(",")

	try:
		index = ids.index(username)
		logger_.info("get_pw username:{}, index:{}".format(username, index))
		return passes[index]
	except ValueError:
		logger_.error('get_pw ', exc_info=True)
		return None

@application.route('/')
#@auth.login_required
def index():
	city = request.args.get('city', default="")
	user = request.cookies.get('user')
	session['city'] = city
	session['user'] = user
	uid = request.cookies.get('uid', None)

	#user = auth.current_user()
	param = {"path":application.config["PATH"], 'user':user}

	return render_template('index.html', params=param)


clientManager_ = {}
progressData_ = {}
cancelRequest_ = {}
WAIT_TIMEOUT = 0.2
TIMEOUT_WAITMSG = 5

class AppCallbackHandler(SimpleHandler):
	def __init__(self, requestId, city, user):
		self.requestId = requestId
		self.summary = ""
		self.tmpbuf = ""
		self.city = city
		self.user = user
		self.encoding = tiktoken.get_encoding('cl100k_base')
		self.count = 0
		self.starttime = None
		self.isLastGenerate = False
		self.progress = 0
		self.total_length = 0

	def on_llm_start(
		self, **kwargs: Any
	) -> None:
		logger_.debug("要約開始")
		self.summary = ""
		self.tmpbuf = ""
		"""for p in prompts:
			self.count += len(self.encoding.encode(p))"""
		self.notify( self.tmpbuf, False, True)

	def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
		if cancelRequest_[self.requestId]:
			logger_.debug(f"on_llm_new_token cancelRequest_[self.requestId]:{cancelRequest_[self.requestId]}")
			raise KeyboardInterrupt
		self.tmpbuf += token
		if token.find('。') >= 0:
			logger_.debug(f"on_llm_new_token {self.tmpbuf}")
			self.notify( self.tmpbuf, False, False)
			self.tmpbuf = ""
		self.summary = token

	def on_llm_end(self, **kwargs: Any) -> None:
		"""Run when LLM ends running."""
		logger_.debug(f"要約終了")
	
	def is_last_generate(self, **kwargs: Any) -> Any:
		logger_.info("最後の生成\n")
		self.isLastGenerate = True

	def show_progress(self,idx: int, total_length: int, **kwargs: Any) -> Any:
		logger_.info(f"現在の進捗 {idx}/{total_length}")
		self.progress = idx
		self.total_length = total_length

	def notify(self, text:str, isEnd:bool, reset:bool):
		try:
			if reset:
				progressData_[self.requestId].put({'error':False, "reset":reset, 'progress':self.progress, 'total':self.total_length, 'is_final':self.isLastGenerate})
			else:
				progressData_[self.requestId].put({'error':False, "summary":text, 'end':isEnd})
			if not cancelRequest_[self.requestId]:
				logger_.debug("AppCallbackHandler - requestId in clientManager_:{}".format(self.requestId in clientManager_))
				if self.requestId in clientManager_:
					condition = clientManager_[self.requestId]
					with condition:
						condition.notify()
					time.sleep(0.05) # スリープしないとスレッドが切り替わらないまま
		except Exception:
			logger_.error("notify", exc_info=True)
	

def getExceptionMsg(exception):
	if isinstance(exception, openai.error.Timeout):
		return "ご迷惑をおかけしております。現在OpenAIのサービスが混み合っているようです。30分ほどお待ちいただいた後、再度お試しください。"
	elif isinstance(exception, openai.error.RateLimitError):
		return "ご迷惑をおかけしております。現在OpenAIのサービスをご利用いただくことができません。1、2時間ほどお待ちいただいた後、再度お試しください。"
	elif isinstance(exception, openai.error.ServiceUnavailableError):
		return "ご迷惑をおかけしております。現在OpenAIのサービスをご利用いただくことができません。復旧するまでお待ちいただくようお願い申し上げます。"
	else:
		return "ご迷惑をおかけしております。原因不明のエラーが発生しました。"


def dosummary(requestId, text, prompt, mode, config, city, user):
	def _notify(requestId):
		global clientManager_
		logger_.debug("dosummary - requestId in clientManager_:{}".format(requestId in clientManager_))
		if requestId in clientManager_:
			condition = clientManager_[requestId]
			with condition:
				condition.notify()
	try:
		global progressData_, clientManager_
		logger_.debug("start of dosummary")
		logger_.debug("dosummary requestId:{}".format(requestId))
		logger_.debug("dosummary mode:{}".format(mode))

		#logger_.debug(f"dosummary MakeSummary_GPT created:{passages}")

		#with open(baseDir / "debug/sections.txt", "w") as f:
		#	f.write(json.dumps(sections,indent=4))
		#logger_.debug(f"dosummary section_list:{section_list}")
		#with open(baseDir / "debug/section_list.txt", "w") as f:
		#	f.write(json.dumps(section_list,indent=4))

		#logger_.debug("dosummary section_list:{}".format(section_list))
		try:
			handler = AppCallbackHandler(requestId, city, user)
			for p in prompt:
				handler.count += len(handler.encoding.encode(p))
			handler.starttime = datetime.datetime.now()
			handler.count = 0

			#gpt_mode = GPT4 if mode == "gpt-4" else GPT35
			if application.config['TEST']:
				lc_summary = LangChainSummaryTest()
			else:
				lc_summary = PartSplitSummary(callback_handler=handler)
			#count = len(encoding.encode(text))
			#count += len(encoding.encode(prompt))

			logger_.debug("dosummary OPENAI_KEYS:{}".format(config['OPENAI_KEYS']))
			model = RoundRobinModel(config)
			base, key = model.get_current_model()
			
			# パラメータの設定
			lc_summary.set_model(
				deployment_name = config['OPENAI_DEPLOYMENT_NAME'],
				api_type = config['OPENAI_API_TYPE'],
				api_base = base,
				api_key = key,
				api_version = config['OPENAI_API_VERSION'])

			res = lc_summary.make_summary(summary_trg=text, prompt_text=prompt)

			span = datetime.datetime.now() - handler.starttime
			handler.count += len(handler.encoding.encode(handler.summary))
			with TokenModel(application.config['TOKEN_MODEL_HOST'], application.config['TOKEN_MODEL_PORT'], 
				application.config['TOKEN_MODEL_DB'], application.config['TOKEN_MODEL_USER'], application.config['TOKEN_MODEL_PASS']) as model:
				logger_.debug(f"self.city:{handler.city}, self.user:{handler.user}, self.count:{handler.count}")
				model.setUsedToken(city, user, handler.count, span)
			handler.notify(handler.tmpbuf, True, False)
			#with TokenModel(application.config['TOKEN_MODEL_HOST'], application.config['TOKEN_MODEL_PORT'], 
		   	#	application.config['TOKEN_MODEL_DB'], application.config['TOKEN_MODEL_USER'], application.config['TOKEN_MODEL_PASS']) as model:
			#	model.setUsedToken(city, user, count)

			#progressData_[requestId].put({'error':False, 'end':True}) # 処理終了の通知
		except  (openai.error.Timeout, openai.error.RateLimitError,openai.error.ServiceUnavailableError, openai.error.APIError, openai.error.APIConnectionError) as e:
			msg = getExceptionMsg(e)
			progressData_[requestId].put({'error':True, 'errormsg':msg}) # エラーの通知
			time.sleep(WAIT_TIMEOUT)

		_notify(requestId)

	except Exception as e:
		logger_.error('dosummary', exc_info=True)
		msg = getExceptionMsg(e)
		progressData_[requestId].put({'error':True, 'errormsg':msg}) # エラーの通知
		time.sleep(WAIT_TIMEOUT)
		_notify(requestId)

	logger_.debug("end of dosummary")

@application.route('/summary',methods=['POST'])
def summary():
	global clientManager_, progressData_, cancelRequest_

	prompt = request.values['prompt']
	text = request.values['text']
	mode = request.values['mode']
	requestId = random.getrandbits(52)
	while requestId in clientManager_:
		requestId = random.getrandbits(52)
	progressData_[requestId] = Queue()
	cancelRequest_[requestId] = False
	logger_.debug("summary - progressData_ is created:{}".format(requestId))
	# start 1 worker processes
	thread = threading.Thread(target=dosummary, args=(requestId, text, prompt, mode, application.config, session['city'], session['user']))
	thread.start()
	return jsonify({'result':True, 'requestId':requestId})

@application.route('/getprogress',methods=['POST'])
def getProgress():
	global clientManager_, progressData_
	requestId = int(request.values['requestId'])
	logger_.debug("getProgress - requestId:{} clientManager_:{} canceled:{}".format(requestId, clientManager_, request.values['canceled']))
	time_start = time.time()
	# conditionの取得
	try:
		condition = None
		if requestId in clientManager_:
			condition = clientManager_[requestId]
			#logger_.debug("getProgress - conditions:{}".format(condition))
		else:
			condition = threading.Condition()
			clientManager_[requestId] = condition
			logger_.debug("getProgress - new condition:{} requestId:{}".format(condition, requestId))

		if request.values['canceled'] == '1':
			cancelRequest_[requestId] = True
			logger_.debug("getProgress - requestId:{} cancelRequest_[requestId]:{}".format(requestId, cancelRequest_[requestId]))
		if not requestId in progressData_:
			logger_.debug("getProgress - requestId:{} progressData_ is not found".format(requestId))
		while (requestId in progressData_ and progressData_[requestId].empty()) and ((time.time() - time_start) < TIMEOUT_WAITMSG):
			with condition:
				condition.wait(WAIT_TIMEOUT)
		
		logger_.debug("getProgress - condition released condition:{}, progressData_:{}".format(condition, progressData_))
		
		#if not (requestId in progressData_):
		#	logger_.debug("getProgress - progressData_ is not found.:{}".format(requestId))
		#	return jsonify({'result':False})	
		
		if requestId in progressData_ and progressData_[requestId].qsize() > 0:
			data = progressData_[requestId].get()
			progressData_[requestId].task_done() 
			logger_.debug("getProgress - data:{} len:{}".format(data, progressData_[requestId].qsize()))
			if 'end' in data and data['end']:
				clientManager_.pop(requestId)
				cancelRequest_.pop(requestId)
				progressData_.pop(requestId)
				logger_.debug("getProgress - data were removed")

			if 'error' in data and data['error']:
				return jsonify({'result':True, 'error':data['error'], 'errormsg':data['errormsg']})
			else:
				if 'reset' in data:
					return jsonify({'result':True, 'reset':data['reset'], 'progress':data['progress'], 'total':data['total'], 'is_final':data['is_final']})
				else:
					return jsonify({'result':True, 'summary':data['summary'], 'end':data['end']})
		else:
			return jsonify({'result':True})
	except:
		logger_.error('getProgress', exc_info=True)
		return jsonify({'result':False})	


@application.errorhandler(Exception)
def error_except(e):
	global logger_
	logger_.error(request.url, exc_info=True)
	return jsonify({'message': 'Exception', 'action': 'call me'}), 500

if __name__=="__main__":
	#application.run(host='0.0.0.0')
	data = toJson(sys.argv[1])
	pprint.pprint(data)
	html = jsonToHtml(data)
	print(html)
