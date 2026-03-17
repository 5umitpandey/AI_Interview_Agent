from datetime import datetime
import logging 
import database


logger = logging.getLogger("interview-agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# -------------------------------------------------
# SIMPLE TRANSCRIPT FILE WRITER
# -------------------------------------------------

class SimpleTranscriptWriter:
    """Dead simple - just write to file immediately every time"""
    
    def __init__(self, room_name: str):
        self.room_name = room_name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.filename = f"transcripts/{self.room_name}_{timestamp}_transcript.txt"
        self.entry_count = 0
        
        # Create file with header
        with open(self.filename, 'w', encoding='utf-8') as f:
            f.write(f"INTERVIEW TRANSCRIPT\n")
            f.write(f"Room: {self.room_name}\n")
            f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
        
        logger.info(f"✅ Transcript file created: {self.filename}")
    
    def write(self, speaker: str, text: str):
        """Write entry immediately to file"""
        try:
            timestamp = datetime.now().isoformat()
            with open(self.filename, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {speaker}:\n{text}\n")
                f.write("-" * 80 + "\n\n")
                f.flush()  # Force write
            
            self.entry_count += 1
            logger.info(f"✅ SAVED: {speaker} (Entry #{self.entry_count})")
            logger.info(f"   Text: {text[:80]}...")
            
            # Also save to database
            try:
                database.add_transcript_entry(self.room_name, speaker, text)
            except Exception as e:
                logger.error(f"DB error: {e}")
                
        except Exception as e:
            logger.error(f"❌ FAILED TO WRITE: {e}")

    def close(self):
        """Finalize the file"""
        try:
            with open(self.filename, 'a', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write(f"INTERVIEW COMPLETED\n")
                f.write(f"Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Entries: {self.entry_count}\n")
                f.write("=" * 80 + "\n")
            
            logger.info(f"✅ Transcript finalized: {self.entry_count} entries saved")
            # database.update_recording_path(self.room_name, self.filename)
            database.save_transcript_file(self.room_name)
            return self.filename
        except Exception as e:
            logger.error(f"Error finalizing: {e}")
            return None