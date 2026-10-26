from database import get_connection

try:
    connection = get_connection()
    print("Oracle Database connected successfully!")

    cursor = connection.cursor()
    cursor.execute("SELECT USER FROM dual")

    result = cursor.fetchone()
    print("Connected user:", result[0])

    cursor.close()
    connection.close()

except Exception as error:
    print("Database connection failed:", error)