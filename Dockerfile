FROM python:3.6
RUN mkdir /app/
COPY application.py /app/application.py
WORKDIR /app
RUN pip install Flask==1.0.2
EXPOSE 5000
CMD ["python", "application.py"]
