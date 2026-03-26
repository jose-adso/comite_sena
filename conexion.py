import psycopg2
import os

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "75.119.147.138"),
        port=os.getenv("DB_PORT", "5430"),
        database=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "H3U15P0LeCr0vTwsCoZNyaG1PLCR9FtMfbQFyaE9ea6VbvbkUtAfWeacxYjfPUTl")
    )

if __name__ == "__main__":
    try:
        conn = get_connection()
        print("✅ Conexión exitosa")
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        print(cursor.fetchone())
        cursor.close()
        conn.close()
    except Exception as e:
        print("❌ Error:", e)
