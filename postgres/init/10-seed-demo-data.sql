\c demo_data;

CREATE SCHEMA IF NOT EXISTS public;

CREATE TABLE IF NOT EXISTS person (
  id SERIAL PRIMARY KEY,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  job_title TEXT NOT NULL,
  ssn TEXT UNIQUE NOT NULL,
  gender TEXT NOT NULL,
  age INTEGER NOT NULL
);

INSERT INTO person (first_name, last_name, job_title, ssn, gender, age) VALUES
('John', 'Smith', 'Software Engineer', '123-45-6789', 'Male', 28),
('Sarah', 'Johnson', 'Data Analyst', '234-56-7890', 'Female', 31),
('Michael', 'Brown', 'Product Manager', '345-67-8901', 'Male', 29),
('Emily', 'Davis', 'UX Designer', '456-78-9012', 'Female', 26),
('David', 'Wilson', 'DevOps Engineer', '567-89-0123', 'Male', 34),
('Lisa', 'Anderson', 'Business Analyst', '678-90-1234', 'Female', 27),
('Robert', 'Taylor', 'QA Engineer', '789-01-2345', 'Male', 33),
('Jennifer', 'Martinez', 'Marketing Specialist', '890-12-3456', 'Female', 25),
('Christopher', 'Garcia', 'Systems Administrator', '901-23-4567', 'Male', 30),
('Amanda', 'Rodriguez', 'Project Coordinator', '012-34-5678', 'Female', 32)
ON CONFLICT (ssn) DO NOTHING;