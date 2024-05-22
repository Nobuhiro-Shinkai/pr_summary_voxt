import psycopg2
import psycopg2.extras
import logging
import datetime 
import argparse 
import requests
import json
import os

#logger_ = logging.getLogger("AmiGraph.model")


class TokenModel:
	def __init__(self, host="", port=0,
					   dbname="", user="",
					   password=""):
		self.conn_ = psycopg2.connect('host={} port={} dbname={} user={} password={}'.format(
			host, port, dbname, user, password))

	def __enter__(self):
		#logger_.debug("__enter__")
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		#logger_.debug("__exit__")
		self.close()
		if (exc_type!=None):
			#return True  #例外を抑制するには
			return False #例外を伝播する

	def close(self):
		#logger_.debug("close()")
		self.conn_.close()
		
	def setUsedToken(self, username, city, token, span):
		with self.conn_.cursor() as cur:
			dt = datetime.datetime.now()
			sql_string = "INSERT INTO tokencount (username, city, date, token, time) VALUES (%s, %s, %s, %s, %s);"
			cur.execute(sql_string, (username, city, dt, token, span,))
			self.conn_.commit()
	
	def getUserAccess(self):
		dt = datetime.datetime.now()
		dt = dt.replace(day=1)
		sql_string = 'SELECT city, SUM(token) from tokencount where date >= %s GROUP BY city;'
		with self.conn_.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
			cur.execute(sql_string, (dt,))
			results = cur.fetchall()
			dict_result = []
			for row in results:
				dict_result.append(dict(row))
			return dict_result		
	
	def deletePrevMonth(self):
		with self.conn_.cursor() as cur:
			dt = datetime.datetime.now()
			dt = dt.replace(day=1)
			last_month_last_day = dt - datetime.timedelta(days=1)
			sql_string = "DELETE FROM tokencount where date <= %s;"
			cur.execute(sql_string, (last_month_last_day,))
			self.conn_.commit()


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('-t', '--test', action='store_true') 
	parser.add_argument('-d', '--delete', action='store_true')
	parser.add_argument('-a', '--aggregate', action='store_true') 
	parser.add_argument('-r', '--threshold') 
	parser.add_argument('-u', '--url') 
	args = parser.parse_args() 

	threshold = 0
	if args.threshold:
		threshold = int(args.threshold)

	url = "https://amivoice.webhook.office.com/webhookb2/fc3790c9-1127-4cc6-958d-53b7cc598036@e2325441-511f-43c8-ad0a-eaebfbe1a8de/IncomingWebhook/fba5ddb1cc744d5ebdf9d03d2c841d89/5e2284c9-725d-4fba-8b23-3a68589562ba"
	if args.url:
		url = args.url

	with TokenModel("localhost", 5432, "tokenmodel", "postgres", "amivoiceamivoice") as model:
		if args.delete:
			model.deletePrevMonth()
		elif args.test:
			model.setUsedToken("11111", "matsudo", 2046)
			model.setUsedToken("11111", "matsudo", 1024)
			model.setUsedToken("22222", "toride", 1024)
			model.setUsedToken("22222", "toride", 1024)
			model.setUsedToken("33333", "toshima", 1024)
			model.setUsedToken("33333", "toshima", 4096)
			model.getUserAccess()
		elif args.aggregate:
			access = model.getUserAccess()
			if len(access) > 1 and access[0]['sum'] > threshold:
				msg = """<table><thead>
					<tr>
						<th >city</th>
						<th >token数</th>
					</tr>
				</thead>
				<tbody>"""
				for a in access:
					msg +=f"<tr><td>{a['city']}</td><td>{a['sum']}</td></tr>"
				msg += "</tbody></table>"
				#send_message = send_message.replace('\n', '<BR>')
				requests.post(url, data=json.dumps({'title': '', 'text': msg}))
