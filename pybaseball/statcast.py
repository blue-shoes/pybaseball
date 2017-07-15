import pandas as pd
import requests
import datetime
import warnings
import io

#TODO: does query work if end_dt befre start_dt? if not, detect this and swap them

def validate_datestring(date_text):
    try:
        datetime.datetime.strptime(date_text, '%Y-%m-%d')
    except ValueError:
        raise ValueError("Incorrect data format, should be YYYY-MM-DD")

def sanitize_input(start_dt, end_dt):
	# if no dates are supplied, assume they want yesterday's data
	# send a warning in case they wanted to specify
	if start_dt is None and end_dt is None:
		today = datetime.datetime.today()
		start_dt = (today - datetime.timedelta(1)).strftime("%Y-%m-%d")
		end_dt = today.strftime("%Y-%m-%d")
		print("Warning: no date range supplied. Returning yesterday's Statcast data. For a different date range, try get_statcast(start_dt, end_dt).")
	#if only one date is supplied, assume they only want that day's stats
	#query in this case is from date 1 to date 1
	if start_dt is None:
		start_dt = end_dt
	if end_dt is None:
		end_dt = start_dt
	# now that both dates are not None, make sure they are valid date strings
	validate_datestring(start_dt)
	validate_datestring(end_dt)
	return start_dt, end_dt

def small_request(start_dt,end_dt):
	url = "https://baseballsavant.mlb.com/statcast_search/csv?all=true&hfPT=&hfAB=&hfBBT=&hfPR=&hfZ=&stadium=&hfBBL=&hfNewZones=&hfGT=R%7CPO%7CS%7C=&hfSea=&hfSit=&player_type=pitcher&hfOuts=&opponent=&pitcher_throws=&batter_stands=&hfSA=&game_date_gt={}&game_date_lt={}&team=&position=&hfRO=&home_road=&hfFlag=&metric_1=&hfInn=&min_pitches=0&min_results=0&group_by=name&sort_col=pitches&player_event_sort=h_launch_speed&sort_order=desc&min_abs=0&type=details&".format(start_dt, end_dt)
	s=requests.get(url, timeout=None).content
	data = pd.read_csv(io.StringIO(s.decode('utf-8')))
	return data

def large_request(start_dt,end_dt,d1,d2):
	"""
	break start and end date into smaller increments, collecting all data in small chunks and appending all results to a common dataframe
	end_dt is the date strings for the final day of the query
	d1 and d2 are datetime objects for first and last day of query, for doing date math
	a third datetime object (d) will be used to increment over time for the several intermediate queries
	"""
	print("This is a large query, it may take a moment to complete")
	dataframe_list = []
	step = 3 # number of days per mini-query (test this later to see how large I can make this without losing data)
	d = d1 + datetime.timedelta(days=step)
	while d <= d2: #while intermediate query end_dt <= global query end_dt, keep looping
		start_dt = d1.strftime('%Y-%m-%d')
		intermediate_end_dt = d.strftime('%Y-%m-%d')
		data = small_request(start_dt,intermediate_end_dt)
		# append to list of dataframes
		dataframe_list.append(data)
		print("Completed sub-query from {} to {}").format(start_dt,intermediate_end_dt)
		# increment dates
		d1 = d1 + datetime.timedelta(days=step+1)
		d = d + datetime.timedelta(days=step+1)

	# if start date > end date after being incremented, the loop captured each date's data
	if d1 > d2:
		pass
	# if start date <= end date, then there are a few leftover dates to grab data for.
	else:
		# start_dt from the earlier loop will work, but instead of d we now want the original end_dt
		start_dt = d1.strftime('%Y-%m-%d')
		data = small_request(start_dt,end_dt)
		dataframe_list.append(data)
		print("Completed sub-query from {} to {}").format(start_dt,end_dt)

	# concatenate all dataframes into final result set 
	final_data = pd.concat(dataframe_list, axis=0)

	#last, convert date col to datetime data type and sort so that this returns in an order that makes sense
	final_data['game_date'] = pd.to_datetime(final_data['game_date'], format='%Y-%m-%d')
	final_data = final_data.sort_values(['game_date'], ascending=False)
	return final_data

def statcast(start_dt=None, end_dt=None, team=None):
	""" 
	Pulls statcast play-level data from Baseball Savant for a given date range.

	INPUTS: 
	start_dt: YYYY-MM-DD : the first date for which you want statcast data
	end_dt: YYYY-MM-DD : the last date for which you want statcast data 
	team: optional (defaults to None) : city abbreviation of the team you want data for (e.g. SEA or BOS)

	If no arguments are provided, this will return yesterday's statcast data. If one date is provided, it will return that date's statcast data. 
	"""
	start_dt, end_dt = sanitize_input(start_dt, end_dt)
	# 3 days or less -> a quick one-shot request. Greater than 3 days -> break it into multiple smaller queries
	small_query_threshold = 3
	# inputs are valid if either both or zero dates are supplied. Not valid of only one given.
	if start_dt and end_dt:
		# how many days worth of data are needed?
		date_format = "%Y-%m-%d"
		d1 = datetime.datetime.strptime(start_dt, date_format)
		d2 = datetime.datetime.strptime(end_dt, date_format)
		days_in_query = (d2 - d1).days
		if days_in_query <= small_query_threshold:
			data = small_request(start_dt,end_dt)
		else:
			data = large_request(start_dt,end_dt,d1,d2)

		#select only pitches from a particular team
		valid_teams = ['MIN', 'PHI', 'BAL', 'NYY', 'LAD', 'OAK', 'SEA', 'TB', 'MIL', 'MIA',
	       'KC', 'TEX', 'CHC', 'ATL', 'COL', 'HOU', 'CIN', 'LAA', 'DET', 'TOR',
	       'PIT', 'NYM', 'CLE', 'CWS', 'STL', 'WSH', 'SF', 'SD', 'BOS'] #get a list
		if(team in valid_teams):
			data = data.loc[(df['home_team']==team)|(data['away_team']==team)]
		elif(team != None):
			raise ValueError('Error: invalid team abbreviation. Valid team names are: {}'.format(valid_teams))
		return data
