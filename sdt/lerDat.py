import duckdb

def lerArquivo(args):
    file_path, file_type = args

    data = duckdb.query(f"""
        SELECT * 
        FROM read_csv_auto('{file_path}',
        ignore_errors=true)
        LIMIT 10
    """).df()

    print(data)