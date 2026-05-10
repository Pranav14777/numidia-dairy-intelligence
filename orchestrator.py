import logging
import time
import sys
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from config import LOG_FILE, SCHEDULE_HOUR, SCHEDULE_MINUTE
from main import run_pipeline

# ── Logging Setup ─────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def pipeline_job():
    """
    Wrapper function that runs the full pipeline.
    Called automatically by the scheduler at the configured time.
    """
    logger.info("=" * 60)
    logger.info("SCHEDULER - Automatic pipeline run triggered")
    logger.info(f"Trigger time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    try:
        run_pipeline()
        logger.info("SCHEDULER - Pipeline completed successfully")
    except Exception as e:
        logger.error(f"SCHEDULER - Pipeline failed: {e}")


def on_job_executed(event):
    """Called when a scheduled job completes successfully."""
    logger.info(
        f"SCHEDULER - Job executed successfully at "
        f"{datetime.now().strftime('%H:%M:%S')}"
    )


def on_job_error(event):
    """Called when a scheduled job fails."""
    logger.error(
        f"SCHEDULER - Job failed at "
        f"{datetime.now().strftime('%H:%M:%S')}: "
        f"{event.exception}"
    )


def start_scheduler():
    """
    Starts the APScheduler background scheduler.
    Runs the pipeline automatically every day at the
    configured time (default: 08:00 AM).

    In production this would run on:
    - Azure Functions
    - Windows Task Scheduler
    - A dedicated server

    For this prototype it runs locally.
    """

    scheduler = BackgroundScheduler()

    # Add event listeners
    scheduler.add_listener(on_job_executed, EVENT_JOB_EXECUTED)
    scheduler.add_listener(on_job_error,    EVENT_JOB_ERROR)

    # Schedule daily pipeline run
    scheduler.add_job(
        func      = pipeline_job,
        trigger   = "cron",
        hour      = SCHEDULE_HOUR,
        minute    = SCHEDULE_MINUTE,
        id        = "dairy_pipeline",
        name      = "Numidia Dairy Intelligence Pipeline",
        misfire_grace_time = 300  # allow 5 min late start
    )

    # Also run immediately on startup so you can demo it
    scheduler.add_job(
        func      = pipeline_job,
        trigger   = "date",
        run_date  = datetime.now(),
        id        = "startup_run",
        name      = "Startup Pipeline Run"
    )

    scheduler.start()

    # Print status
    print("\n")
    print("=" * 60)
    print("  NUMIDIA PIPELINE ORCHESTRATOR")
    print("=" * 60)
    print(f"  Status     : RUNNING")
    print(f"  Started    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Daily run  : Every day at "
          f"{SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} AM")
    print(f"  Next run   : {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} tomorrow")
    print("=" * 60)
    print("  Press Ctrl+C to stop the scheduler")
    print("=" * 60)
    print("\n")

    logger.info(
        f"Scheduler started - pipeline runs daily at "
        f"{SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d}"
    )

    # Keep the scheduler alive
    try:
        while True:
            now = datetime.now()
            next_run = (
                f"Next scheduled run: today at "
                f"{SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d}"
                if now.hour < SCHEDULE_HOUR
                else f"Next scheduled run: tomorrow at "
                f"{SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d}"
            )
            print(
                f"  [{now.strftime('%H:%M:%S')}] "
                f"Scheduler active. {next_run}",
                end="\r"
            )
            time.sleep(60)  # update status every minute

    except KeyboardInterrupt:
        print("\n\n  Stopping scheduler...")
        scheduler.shutdown()
        logger.info("Scheduler stopped by user")
        print("  Scheduler stopped cleanly.")
        print("=" * 60)
        sys.exit(0)


if __name__ == "__main__":
    start_scheduler()