from db import run_query

# Insert sample data
run_query("INSERT INTO customers (name, email, city) VALUES ('Aman', 'aman@gmail.com', 'Delhi')")
run_query("INSERT INTO customers (name, email, city) VALUES ('Ravi', 'ravi@gmail.com', 'Mumbai')")

# Verify data
results, columns = run_query('SELECT * FROM customers;')
print('Database setup complete!')
print('Customers:', results)
