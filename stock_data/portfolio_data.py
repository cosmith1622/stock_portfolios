import pandas as pd
import numpy as np
import os
from stock_data import stock_data
from stock_data import stock_data_connector
from stock_data import s3_connector
from datetime import date, timedelta
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import io


class portfolio_data:
    def __init__(self):
        self.s3 = s3_connector()
        self.sd = stock_data()

    def get_latest_stock_data(self, bucket):

        """
            grab the latest date we have for each stock
            check to see if the data is already in s3, if not go
            to the database pull the data.
            Then upload the data to the s3 bucket
            and return the data to the caller

        """
        #try:
        print('getting latest data....')
        today = date.today().strftime("%Y-%m-%d")
        latest_stock_data_file_name = f"{today}_latest_stock_data"
        latest_stock_data_file_path = f"./{today}_latest_stock_data.csv"
            #self.s3.download_file(bucket,latest_stock_data_file_name,latest_stock_data_file_path)
            #df = pd.read_csv(latest_stock_data_file_path)

        #except Exception as e:

            #print(f"{latest_stock_data_file_name} not found in s3 {bucket}, we will pull the data")
        try:
            sdc = stock_data_connector()
            conn = sdc.connector.connect(host=os.environ['db_host'],
                                        database=os.environ['db_database'],
                                        port=os.environ['db_port'], 
                                        user=os.environ['db_user'], 
                                        password=os.environ['db_password'])
            cursor = conn.cursor()
            cursor.execute("Select max(trading_date) as trading_date, ticker From dev.public.stock_history Group by ticker")
            data = cursor.fetchall()
            df = pd.DataFrame(data)
            #df.to_csv(latest_stock_data_file_path, index=False)
            #self.s3.upload_file(latest_stock_data_file_path,bucket,latest_stock_data_file_name)
            #df = pd.read_csv(latest_stock_data_file_path)

        except Exception as e:
            print(e)
            raise e
        finally:
            if conn != None:
                conn.close()
                sdc = None
        return df #will need to update back to a list object
    

    def get_latest_equities_data(self,bucket):

        """
            check to see if the equities file is already
            in s3,if it is download the file from s3, if not
            pull the data from the api and upload to s3 and return
            the data to the caller
        
        """

        #try:
        today = date.today().strftime("%Y-%m-%d")
        find_equities_file_name = f"{today}_find_equities"
        find_equities_file_path = f"./{today}_find_equities.csv"
        #self.s3.download_file(bucket,find_equities_file_name,find_equities_file_path)
        #df = pd.read_csv(find_equities_file_path)
        #except Exception as e:
        try:
            self.sd = stock_data()
            df = self.sd.find_equities(25)
            df['start_date'] = date(2000,1,1)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            #df.to_csv(find_equities_file_path, index=False)
            self.s3.put_object(csv_buffer,bucket,find_equities_file_name)
            #self.s3.upload_file(find_equities_file_path,bucket,find_equities_file_name)
            #df = pd.read_csv(find_equities_file_path)
        except Exception as e:
            print(e)
            raise e
        return df


    def get_stock_data(self, stock_data, equity_data, bucket):

        #get variables that you later you to name a csv
        # and upload to s3 bucket
        today = date.today().strftime("%Y-%m-%d")
        price_data_file_name = f"{today}_price_data"
        price_data_file_path = f"./{today}_price_data.csv"
        labeled_list = []
        stocks_db = []
        unique_dates = set()

        #create objects to represent 
        #the stocks and dates that represent the
        #most recent data in the database
        for items in stock_data.values.tolist():
            labeled_list.append({'date':items[0], 'ticker':items[1]})
            stocks_db.append(items[1])
            unique_dates.add(items[0])

        #return the unique list of stocks that are new
        #we eliminate the stocks that already in the database
        new_stocks = list(set(equity_data['symbol'].to_list())-set(stocks_db))

        #create a list of the new stocks with a start date
        #of the 1/1/2000
        for symbol in new_stocks:
            labeled_list.append({'date':date(2000,1,1), 'ticker':symbol})
        unique_dates.add(date(2000,1,1))

        new_data = pd.DataFrame(data=labeled_list)
        prices_list = []
        list_of_dates = list(unique_dates)
        #return the stock data stocks
        #the stocks are group based on 
        #their latest stock data in the database
        #or its is new we use 1/1/2000
        for ddate in list_of_dates:

            list_of_stocks = new_data.loc[new_data['date']==ddate]
            list_of_stocks = list_of_stocks['ticker'].unique().tolist()
            print(f"{ddate} has {len(list_of_stocks)} stocks")
            if ddate != date(2000,1,1):
                start_date = datetime.strptime(ddate.strftime("%Y-%m-%d"), "%Y-%m-%d").date() + timedelta(days=1)
            else:
                    start_date = ddate
            try:
                price_df = self.sd.get_stocks(stocks=list_of_stocks, start=start_date, auto_adjust=True, threads=True)
                price_df['Volume'] = price_df['Volume'].astype(int)
                prices_list.append(price_df)

            except Exception as e:
                print(e)

        prices_df = pd.concat(prices_list)
        csv_buffer = io.StringIO()
        prices_df.to_csv(csv_buffer, index=False)
        #prices_df.to_csv(price_data_file_path, index=False)
        self.s3.put_object(csv_buffer,bucket,price_data_file_name)

    def insert_price_data(self, bucket):

        #create the query for uploading the data
        today = date.today().strftime("%Y-%m-%d")
        price_data_file_name = f"{today}_price_data"     
        upload = f"copy stock_history (trading_date, open_price, high_price, low_price, close_price, volume, ticker) from 's3://{bucket}/{price_data_file_name}' iam_role default IGNOREHEADER 1 csv;"   

        #copy the data from S3 to the redshift database
        try:
            sdc = stock_data_connector()
            conn = sdc.connector.connect(host=os.environ['db_host'],
                                database=os.environ['db_database'],
                                port=os.environ['db_port'], 
                                user=os.environ['db_user'], 
                                password=os.environ['db_password'])
            cursor = conn.cursor()
            cursor.execute(upload)
            conn.commit()
        except Exception as e:
            print(e)
        finally:
            if conn != None:
                conn.close()
                sdc = None

    def get_stocks_without_info(self):  

        #grab the latest stocks from the stock_history
        #where it doesn't exist in the stock info
        #we do this to avoid creating duplicates
        try:
            sdc = stock_data_connector()
            conn = sdc.connector.connect(host=os.environ['db_host'],
                                database=os.environ['db_database'],
                                port=os.environ['db_port'], 
                                user=os.environ['db_user'], 
                                password=os.environ['db_password'])
            cursor = conn.cursor()
            cursor.execute("Select distinct ticker \
                            From dev.public.stock_history \
                            where ticker not in (Select distinct ticker from  dev.public.stock_info)")
            data = cursor.fetchall()
            df = pd.DataFrame(data)
        except Exception as e:
            print(e)
        finally:
            if conn != None:
                conn.close()
                sdc = None
        return df

    def insert_stock_data(self, bucket):

        #create the query for uploading the data
        today = date.today().strftime("%Y-%m-%d")
        price_data_file_name = f"{today}_find_equities"     
        upload = f"copy stock_info (ticker, industry, industry_key, industry_disp,sector, sector_key, sector_disp, type_disp,quote_type, currency, full_exhange_name, market) from 's3://{bucket}/{price_data_file_name}' iam_role default IGNOREHEADER 1 csv;"   

        #copy the data from S3 to the redshift database
        try:
            sdc = stock_data_connector()
            conn = sdc.connector.connect(host=os.environ['db_host'],
                                database=os.environ['db_database'],
                                port=os.environ['db_port'], 
                                user=os.environ['db_user'], 
                                password=os.environ['db_password'])
            cursor = conn.cursor()
            cursor.execute(upload)
            conn.commit()
        except Exception as e:
            print(e)
        finally:
            if conn != None:
                conn.close()
                sdc = None
