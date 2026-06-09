import asyncio
import logging
import os
import time
from typing import Optional

import database
from utils.export import load_csv

logger = logging.getLogger(__name__)

_scheduler_task: Optional[asyncio.Task] = None


async def _run_job(job: dict, pool, bot):
    job_id = job["id"]
    await database.job_update_status(job_id, "running")
    logger.info("Running scheduled job %d (mode=%s)", job_id, job["mode"])
    try:
        if not os.path.exists(job["csv_path"]):
            raise FileNotFoundError(f"CSV not found: {job['csv_path']}")
        users = await load_csv(job["csv_path"])
        if not users:
            raise ValueError("CSV is empty")

        from modules import sender as S
        mode = job["mode"]
        template = job["template"]
        photo = job.get("photo_path") or ""
        button = job.get("button") or ""

        if mode == "userbot":
            stats = await S.via_userbot(
                pool, users, template,
                photo_path=photo or None,
                button=button or None,
            )
        else:
            bots = await database.get_bot_tokens()
            tokens = [b["token"] for b in bots]
            if not tokens:
                raise ValueError("No bot tokens available")
            stats = await S.via_bot(
                tokens, users, template,
                photo_path=photo or None,
                button=button or None,
            )

        await database.job_update_status(job_id, "done")
        await database.log_stat("send", f"sched:{mode}", stats["success"])
        logger.info("Job %d done: %s", job_id, stats)

        import config
        summary = (
            f"✅ Плановая рассылка #{job_id} завершена\n"
            f"📤 Отправлено: {stats['success']}/{stats['total']}"
        )
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, summary)
            except Exception:
                pass

    except Exception as e:
        logger.error("Scheduled job %d failed: %s", job_id, e)
        await database.job_update_status(job_id, "failed")
        import config
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, f"❌ Плановая рассылка #{job_id} ошибка:\n{e}", parse_mode=None)
            except Exception:
                pass


async def _scheduler_loop(pool, bot):
    while True:
        try:
            now = int(time.time())
            jobs = await database.job_get_pending()
            for job in jobs:
                if job["run_at"] <= now:
                    asyncio.create_task(_run_job(job, pool, bot))
        except Exception as e:
            logger.error("Scheduler loop error: %s", e)
        await asyncio.sleep(30)


def start_scheduler(pool, bot):
    global _scheduler_task
    _scheduler_task = asyncio.create_task(_scheduler_loop(pool, bot))
    logger.info("Scheduler started")


def stop_scheduler():
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        _scheduler_task = None
