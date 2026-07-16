"""Minimal Coze workflow example.

The workflow token is read from `COZE_API_TOKEN` so the file no longer
contains a hard-coded credential.
"""

from __future__ import annotations

import os


WORKFLOW_ID = os.getenv("COZE_WORKFLOW_ID", "7631960420115513395")
APP_ID = os.getenv("COZE_APP_ID", "7631897074438815787")


def main() -> None:
    try:
        from cozepy import COZE_CN_BASE_URL, Coze, Stream, TokenAuth, WorkflowEvent, WorkflowEventType
    except ImportError as exc:
        raise SystemExit("Install `cozepy` to run this example.") from exc

    coze_api_token = os.getenv("COZE_API_TOKEN")
    if not coze_api_token:
        raise SystemExit("Set COZE_API_TOKEN before running this example.")

    coze_api_base = os.getenv("COZE_API_BASE", COZE_CN_BASE_URL)
    coze = Coze(auth=TokenAuth(token=coze_api_token), base_url=coze_api_base)

    def handle_workflow_iterator(stream: Stream[WorkflowEvent]):
        for event in stream:
            if event.event == WorkflowEventType.MESSAGE:
                print("got message", event.message)
            elif event.event == WorkflowEventType.ERROR:
                print("got error", event.error)
            elif event.event == WorkflowEventType.INTERRUPT:
                handle_workflow_iterator(
                    coze.workflows.runs.resume(
                        workflow_id=WORKFLOW_ID,
                        event_id=event.interrupt.interrupt_data.event_id,
                        resume_data="hey",
                        interrupt_type=event.interrupt.interrupt_data.type,
                    )
                )

    handle_workflow_iterator(
        coze.workflows.runs.stream(
            workflow_id=WORKFLOW_ID,
            app_id=APP_ID,
            parameters={
                "BOT_USER_INPUT": "",
                "img": "{}",
                "logo_img": "",
                "logo_place": "",
                "prompt": "一瓶放在沙滩上的可乐",
                "propotion": "1",
                "qr_img": "",
                "qr_place": "",
            },
        )
    )


if __name__ == "__main__":
    main()
