from conexion import get_connection

conn = get_connection()
cur = conn.cursor()

# Check exact column names with case
cur.execute("SELECT attname FROM pg_attribute WHERE attrelid = 'grabacion'::regclass AND attnum > 0")
print("Actual columns in database:")
for row in cur.fetchall():
    print(f"  {row[0]}")

# Check if fecha_registro exists
cur.execute("SELECT 1 FROM pg_attribute WHERE attrelid = 'grabacion'::regclass AND attname = 'fecha_registro'")
print(f"\nfecha_registro exists: {cur.fetchone() is not None}")

cur.close()
conn.close()