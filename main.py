import requests
import json
import datetime
import time
import re
import os
import sys
import logging



def get_lot_details(url):
	response = requests.request("GET", url)

	if response.status_code == 200:
		html = response.text

		# Get first instance of lotid
		raw_lotid = re.search(r"\"activeLotId\":\"[0-9]+\"", html)

		# Extract id from match
		lotid = int(re.sub(r"[^0-9]", "", raw_lotid.group()))

		# Get first instance of tsExpires
		raw_endts = re.search(r"\"tsExpires\":\"[0-9\-T:\+]+\"", html)

		# Extract ts from match
		endts = re.search(r"[0-9]+[0-9\-T:\+]+", raw_endts.group()).group()

		# Cast to datetime
		endts = datetime.datetime.strptime(re.sub(":","",endts), "%Y-%m-%dT%H%M%S%z").timestamp()

		return lotid,endts


def update_lot(lot_id, url):
	payload = json.dumps({
	  "api": "catalog",
	  "method": "getLotDetails",
	  "lotId": lot_id
	})
	headers = {
	  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.7113.93 Safari/537.36',
	  'Accept': '*/*',
	  'Accept-Language': 'en-US,en;q=0.5',
	  'Accept-Encoding': 'gzip, deflate, br',
	  'X-Requested-With': 'XMLHttpRequest',
	  'Content-Type': 'application/json',
	  'Origin': 'https://www.vakantieveilingen.nl',
	  'DNT': '1',
	  'Connection': 'keep-alive',
	  'Referer': 'https://www.vakantieveilingen.nl/veilingen/hotels/luxe-hotels/leonardo-hotels--2021/8362',
	  'Sec-Fetch-Dest': 'empty',
	  'Sec-Fetch-Mode': 'cors',
	  'Sec-Fetch-Site': 'same-origin',
	  'TE': 'trailers',
	}

	response = requests.request("POST", url, headers=headers, data=payload)

	if response.status_code == 200:
		js = json.loads(response.text)

		if len(js["errors"]) > 0:
			errors = js["errors"]
			logging.info("Got errors:")
			for err in errors:
				logging.info(err["code"],err["description"])
		else:
			data = js["data"]
			winr = data["hasWinner"]

			bids = data["bidHistory"]

			lastbid = {
				"first_name": None,
				"last_name": None,
				"bid": 0,			
			}
			if len(bids) > 0:
				lastbid_data = bids[0]
				lastbid["first_name"] = lastbid_data['customer']['firstName']
				lastbid["last_name"] = lastbid_data['customer']['lastName']
				lastbid["bid"] = lastbid_data['price']

			return winr, len(bids), lastbid
	else:
		logging.debug(f"Wrong status code: {response.status_code}")
		logging.debug(f"Text: {response.text}")


def main(mainurl):
	# mainurl = "https://www.vakantieveilingen.nl/veilingen/hotels/luxe-hotels/leonardo-hotels--2021/8362"
	# mainurl = "https://www.vakantieveilingen.nl/veilingen/producten/elektronica/koptelefoon-hyundai-zwart-noise-cancelling/19637"
	# mainurl = "https://www.vakantieveilingen.nl/veilingen/producten/elektronica/boombox-36-w-techbird/17628"
	# mainurl = "https://www.vakantieveilingen.nl/veilingen/eten-en-drinken/vlees-en-vis/kippendijfilets-thuisbezorgd/20294"

	name = mainurl.split("/")[-2]
	outpath = f"output/{name}.csv"
	nowts = datetime.datetime.now().timestamp()
	nowdate = datetime.datetime.fromtimestamp(nowts)

	# Create logger
	logging.basicConfig(level=logging.DEBUG,
			format='%(asctime)s %(levelname)s %(message)s',
      		filename=f"logs/{name}_{nowdate.strftime('%d_%m_%Y')}.log",
      		filemode='a')

	try:
		# Iterate until there are no auctions anymore
		# TODO: add auction stop clause
		while True:
			logging.info(f"New auction: {name}")

			# Get lot meta-info
			lotid, endts = get_lot_details(mainurl)
			timediff = (endts - nowts) / 60
			logging.info("Lot ID: {lotid}, still have {ts:.2f} minutes to go".format(lotid=lotid,ts=timediff))

			# Get lot biddings until auction is done
			done = False

			while not done:
				msts = int(nowts * 1000)
				url = f"https://www.vakantieveilingen.nl/api.json?{msts}&m=getLotDetails&v={msts}&js=1"
				winr, bidcount, topbid = update_lot(lotid, url)

				if winr: # Save winning bid info
					logging.debug("We have a winner!")
					logging.info(f"Winning bid: {topbid['first_name']} {topbid['last_name']} - {topbid['bid']}")
					logging.debug("Saving...")

					# Append to csv file
					if not os.path.exists(outpath):
						f = open(outpath, "w")

						# Create header
						f.write("Timestamp,firstName,lastName,bid,bidcount\n")
						f.close()

					with open(outpath, "a") as f:
						f.write(",".join([str(i) for i in [
								msts,
								topbid["first_name"],
								topbid["last_name"],
								topbid["bid"],
								bidcount
								]]) + '\n')

					done = True
				elif topbid: # Sleep until auction is over
					logging.debug("No winner yet")
					logging.debug(f"Top bid: {topbid['first_name']} {topbid['last_name']} - {topbid['bid']}")

					time.sleep(timediff * 60)
				else:
					logging.debug("Something went wrong in getting bid info, getting new info")
					done = True
	except:
		logging.error("Got exception on main handler")
		raise


if __name__ == '__main__':
	main(*sys.argv[1:])
