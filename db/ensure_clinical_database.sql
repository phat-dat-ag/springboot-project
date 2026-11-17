-- psql script: creates only a missing database; never resets an existing one.
SELECT format('CREATE DATABASE %I', :'database_name')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'database_name')
\gexec
