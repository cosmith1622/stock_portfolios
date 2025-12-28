FROM python:3.11-slim-bullseye

# Create the directory
RUN mkdir -p /usr/local/app

RUN mkdir -p /home/app/.aws

#create user to run application as non root user
RUN useradd app

# Change ownership of the directory to the non-root user
RUN chown -R app /usr/local/app
RUN chown -R app /home/app/.aws


#switch to working directory, prior to moving 
#project into docker container
WORKDIR /usr/local/app


# Install the application dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


#copy the project to the container
COPY ./stock_data  ./stock_data
COPY main.py ./


# Setup an app user so the container doesn't run as the root user
#RUN useradd app
USER app

CMD ["python", "main.py"] 