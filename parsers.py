import re

class ScanParser:
    @staticmethod
    def parse(summary_text):
        """
        Parses ClamAV scan summary text.
        Returns a dict with parsed values.
        """
        data = {
            "known_viruses": "N/A",
            "engine_version": "N/A",
            "scanned_directories": "0",
            "scanned_files": "0",
            "infected_files": 0,
            "data_scanned": "N/A",
            "data_read": "N/A",
            "time": "N/A",
            "start_date": "N/A",
            "end_date": "N/A",
            "status": "Unknown"
        }
        
        if not summary_text:
            return data

        patterns = {
            "known_viruses": r"Known viruses: (\d+)",
            "engine_version": r"Engine version: ([\d\.]+)",
            "scanned_directories": r"Scanned directories: (\d+)",
            "scanned_files": r"Scanned files: (\d+)",
            "infected_files": r"Infected files: (\d+)",
            "data_scanned": r"Data scanned: ([\d\.]+ [A-Z]+)",
            "data_read": r"Data read: (.*)",
            "time": r"Time: (.*)",
            "start_date": r"Start Date: (.*)",
            "end_date": r"End Date:   (.*)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, summary_text)
            if match:
                val = match.group(1).strip()
                if key == "infected_files":
                    data[key] = int(val)
                else:
                    data[key] = val
        
        if "Scan finished: Clean" in summary_text:
            data["status"] = "Clean"
        elif "Scan finished: INFECTION FOUND" in summary_text or data["infected_files"] > 0:
            data["status"] = "Infected"
        
        return data

class UpdateParser:
    @staticmethod
    def parse(log_text):
        """
        Parses Freshclam update log.
        Returns dict with status and details for each DB.
        """
        result = {
            "status": "Unknown", # Success, Failed, Up-to-date
            "databases": []
        }
        
        if not log_text:
            return result

        if "update process started" in log_text:
            result["status"] = "Finished" # refined later

        dbs = ["daily", "main", "bytecode"]
        
        for db in dbs:
            db_info = {"name": db, "status": "Unknown", "version": "N/A"}
            
            updated_match = re.search(fr"{db}\.(cld|cvd) updated \(version: (\d+)", log_text)
            
            uptodate_match = re.search(fr"{db}\.(cld|cvd) database is up-to-date \(version: (\d+)", log_text)
            
            if updated_match:
                db_info["status"] = "Updated"
                db_info["version"] = updated_match.group(2)
            elif uptodate_match:
                db_info["status"] = "Up-to-date"
                db_info["version"] = uptodate_match.group(2)
            else:
                pass
            
            result["databases"].append(db_info)

        if "ERROR:" in log_text or "Update failed" in log_text:
            result["status"] = "Failed"
        elif any(d["status"] == "Updated" for d in result["databases"]):
            result["status"] = "Success"
        elif all(d["status"] == "Up-to-date" for d in result["databases"]):
             result["status"] = "Up-to-date"
             
        return result
