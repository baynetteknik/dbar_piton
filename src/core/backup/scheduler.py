import os
import subprocess

from src.core.backup.exceptions import SchedulerError


class BackupScheduler:
    """Manages periodic OS-level task registrations (Windows Task Scheduler / Linux Crontab)."""

    @staticmethod
    def register_daily_backup(
        task_name: str,
        python_path: str,
        script_path: str,
        run_time: str = "22:00",
    ) -> None:
        """Schedules a daily backup job at the specified HH:MM time.

        Raises SchedulerError on failure.
        """
        script_path = os.path.abspath(script_path)
        python_path = os.path.abspath(python_path)

        if os.name == "nt":
            # Windows schtasks configuration
            cmd = [
                "schtasks",
                "/create",
                "/tn",
                task_name,
                "/tr",
                f'"{python_path}" "{script_path}"',
                "/sc",
                "daily",
                "/st",
                run_time,
                "/f",
            ]
            try:
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    shell=True,
                )
                if res.returncode != 0:
                    raise SchedulerError(
                        f"Windows schtasks creation failed: {res.stderr.strip()}",
                    )
            except Exception as e:
                if isinstance(e, SchedulerError):
                    raise e
                raise SchedulerError(
                    f"Failed to execute schtasks subprocess: {e}",
                ) from e
        else:
            # POSIX crontab configuration
            parts = run_time.split(":")
            hour = parts[0] if len(parts) > 0 else "22"
            minute = parts[1] if len(parts) > 1 else "00"

            cron_entry = (
                f"{minute} {hour} * * * \"{python_path}\" \"{script_path}\"\n"
            )

            try:
                # Read existing crontab
                cur_cron = subprocess.run(
                    ["crontab", "-l"],
                    capture_output=True,
                    text=True,
                )
                cron_content = (
                    cur_cron.stdout if cur_cron.returncode == 0 else ""
                )

                # Strip previous entries of the same script path to prevent duplicate schedule loops
                lines = cron_content.splitlines()
                new_lines = [
                    line for line in lines if script_path not in line and line
                ]
                new_lines.append(cron_entry.strip())

                new_cron = "\n".join(new_lines) + "\n"

                # Write updated entries back to crontab stdin
                p = subprocess.Popen(
                    ["crontab", "-"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                _, stderr = p.communicate(input=new_cron)
                if p.returncode != 0:
                    raise SchedulerError(
                        f"Linux crontab write failed: {stderr.strip()}",
                    )
            except Exception as e:
                if isinstance(e, SchedulerError):
                    raise e
                raise SchedulerError(
                    f"Failed to update Unix crontab configuration: {e}",
                ) from e

    @staticmethod
    def unregister_backup(task_name: str, script_path: str | None = None) -> None:
        """Deletes scheduled backup job.

        On Unix, script_path is used to identify the cron entry.
        Raises SchedulerError on failure.
        """
        if os.name == "nt":
            # Windows task deletion
            cmd = ["schtasks", "/delete", "/tn", task_name, "/f"]
            try:
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    shell=True,
                )
                # Ignore warning if task didn't exist (exit code 1 with specific messages),
                # but raise on other structural failures.
                if (
                    res.returncode != 0
                    and "NOT FOUND" not in res.stderr.upper()
                    and "BULUNAMADI" not in res.stderr.upper()
                ):
                    raise SchedulerError(
                        f"Windows schtasks deletion failed: {res.stderr.strip()}",
                    )
            except Exception as e:
                if isinstance(e, SchedulerError):
                    raise e
                raise SchedulerError(
                    f"Failed to delete Windows scheduled task: {e}",
                ) from e
        else:
            # POSIX crontab deletion
            if not script_path:
                return

            script_path = os.path.abspath(script_path)
            try:
                cur_cron = subprocess.run(
                    ["crontab", "-l"],
                    capture_output=True,
                    text=True,
                )
                if cur_cron.returncode != 0:
                    return  # No crontab active

                lines = cur_cron.stdout.splitlines()
                new_lines = [
                    line for line in lines if script_path not in line and line
                ]

                if not new_lines:
                    # Clear crontab entirely
                    subprocess.run(
                        ["crontab", "-r"],
                        capture_output=True,
                    )
                else:
                    new_cron = "\n".join(new_lines) + "\n"
                    p = subprocess.Popen(
                        ["crontab", "-"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    _, stderr = p.communicate(input=new_cron)
                    if p.returncode != 0:
                        raise SchedulerError(
                            f"Linux crontab deletion failed: {stderr.strip()}",
                        )
            except Exception as e:
                if isinstance(e, SchedulerError):
                    raise e
                raise SchedulerError(
                    f"Failed to remove crontab entry: {e}",
                ) from e
