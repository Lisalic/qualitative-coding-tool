import asyncio
import gc

from backend.app.jobs.runner import AsyncioJobRunner, get_job_runner


class TestAsyncioJobRunnerSubmit:
    async def test_submitted_coroutine_runs_to_completion(self) -> None:
        runner = AsyncioJobRunner()
        results: list[int] = []

        async def work() -> None:
            results.append(1)

        runner.submit(work())
        # submit() is fire-and-forget; yield control so the scheduled task runs.
        for _ in range(3):
            await asyncio.sleep(0)

        assert results == [1]

    async def test_task_is_removed_from_tracking_set_once_done(self) -> None:
        runner = AsyncioJobRunner()

        async def work() -> None:
            pass

        runner.submit(work())
        assert len(runner._tasks) == 1
        for _ in range(3):
            await asyncio.sleep(0)

        assert len(runner._tasks) == 0

    async def test_tasks_not_garbage_collected_before_completion(self) -> None:
        """The footgun this class exists to prevent: a bare
        ``asyncio.create_task(coro)`` with no reference held anywhere can be
        garbage-collected (and silently cancelled) before it finishes. This
        test submits several coroutines, keeps no reference to whatever
        ``submit()`` returns (it returns ``None`` anyway), forces a few GC
        passes, and confirms every one of them still completes -- which only
        works because ``AsyncioJobRunner`` holds its own reference in
        ``self._tasks`` until each task's done-callback fires.
        """
        runner = AsyncioJobRunner()
        completed: list[int] = []

        async def slow_work(n: int) -> None:
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            completed.append(n)

        for n in range(5):
            runner.submit(slow_work(n))
            # Force GC points between submissions -- if tasks weren't held
            # by reference in `runner._tasks`, this is where they'd die.
            gc.collect()

        gc.collect()
        for _ in range(10):
            await asyncio.sleep(0)
        gc.collect()

        assert sorted(completed) == [0, 1, 2, 3, 4]


class TestGetJobRunner:
    def test_returns_singleton(self) -> None:
        assert get_job_runner() is get_job_runner()

    def test_returns_asyncio_job_runner_instance(self) -> None:
        assert isinstance(get_job_runner(), AsyncioJobRunner)
