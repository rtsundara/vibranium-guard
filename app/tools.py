import csv
import os

def get_log_entry(index: int) -> dict:
    """Reads a proxy log entry from the CSV dataset.
    
    Args:
        index: The zero-based row index to retrieve.
        
    Returns:
        dict with log entry data.
    """
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'proxy_logs.csv')
    try:
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if 0 <= index < len(rows):
                return {"status": "success", "log_entry": rows[index]}
            else:
                return {"status": "error", "message": f"Index {index} out of bounds."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
