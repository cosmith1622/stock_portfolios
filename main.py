from stock_data import portfolio_data


if __name__ == "__main__":


    """
        Step 1 Get the latest stock date in the database.
        If that stock exist in Step 2, we will get the 
        latest information for the stock.

    """
    pdata = portfolio_data()
    data =  pdata.get_latest_stock_data('stock-bucket-01')

    """
        Step 2 get updated stock information for the stocks
        that should be evaluated based on the conditions in the 
        find_equities method and create a csv.  Then push the 
        csv into an s3 bucket

    """

    df = pdata.get_latest_equities_data('stock-bucket-01')


    """

    Step 4
    create a list of all the stocks in the database and
    their last date of data and append it to the new stocks
    with their first date of data we will collect from

    create a unqiue list of start dates for pulling
    new stock data.  We will later use this to group
    stocks with the same starting point to pull data
    in parallel based on starting point

    Then push the data into an s3 bucket

    """

    pdata.get_stock_data(data,df,'stock-bucket-01')



    """
        Push the new stock data into the redshift db

    """
    pdata.insert_data('stock-bucket-01')
