\set db_name `echo $DB_NAME`
\set db_user `echo $DB_USER`
\set db_password `echo $DB_PASSWORD`
CREATE DATABASE :db_name;
CREATE USER :db_user WITH PASSWORD :'db_password';
ALTER ROLE :db_user SET client_encoding TO 'utf8';
ALTER ROLE :db_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE :db_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE :db_name TO :db_user;