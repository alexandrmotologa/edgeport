"""Textual views and widgets for request stream inspection."""

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Label, ListItem, Static

from edgeport.client.storage import CapturedTransaction


class TransactionItem(ListItem):
    """A list item representing an intercepted HTTP transaction."""

    def __init__(self, transaction: CapturedTransaction) -> None:
        super().__init__()
        self.transaction = transaction

    def compose(self) -> ComposeResult:
        method = self.transaction.method.upper()
        status = self.transaction.response_status
        path = self.transaction.path
        duration = f"{self.transaction.duration_ms:.0f}ms"

        # Method badge styling
        method_style = {
            "GET": "bold blue",
            "POST": "bold green",
            "PUT": "bold yellow",
            "DELETE": "bold red",
            "PATCH": "bold magenta",
        }.get(method, "bold white")

        # Status badge styling
        if 200 <= status < 300:
            status_style = "green"
        elif 300 <= status < 400:
            status_style = "cyan"
        elif 400 <= status < 500:
            status_style = "yellow"
        else:
            status_style = "bold red"

        provider = f"[{self.transaction.provider_hint}] " if self.transaction.provider_hint else ""
        label_text = (
            f"[{method_style}]{method:<6}[/] "
            f"[{status_style}]{status}[/] "
            f"[dim]{provider}[/]{path} "
            f"[dim]{duration}[/]"
        )
        yield Label(label_text)


class TransactionDetailView(Vertical):
    """Renders headers, payloads, and timing of the currently selected transaction."""

    def __init__(self) -> None:
        super().__init__()
        self._current_txn: CapturedTransaction | None = None

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="detail-scroll"):
            yield Static("Select a request on the left to inspect details.", id="detail-content")

    def update_transaction(self, txn: CapturedTransaction | None) -> None:
        self._current_txn = txn
        content_widget = self.query_one("#detail-content", Static)

        if not txn:
            content_widget.update("No request selected.")
            return

        lines = [
            f"[bold]Method:[/] {txn.method}  [bold]Path:[/] {txn.full_url}",
            f"[bold]Status:[/] {txn.response_status}  [bold]Latency:[/] {txn.duration_ms:.1f}ms",
            "",
            "[bold underline]Request Headers:[/]",
        ]
        for k, v in txn.request_headers.items():
            lines.append(f"  [cyan]{k}:[/] {v}")

        if txn.request_body:
            lines.extend([
                "",
                "[bold underline]Request Body:[/]",
                f"[dim]{txn.formatted_request_body}[/]",
            ])

        lines.extend([
            "",
            "[bold underline]Response Headers:[/]",
        ])
        for k, v in txn.response_headers.items():
            lines.append(f"  [cyan]{k}:[/] {v}")

        if txn.response_body:
            lines.extend([
                "",
                "[bold underline]Response Body:[/]",
                f"[dim]{txn.formatted_response_body}[/]",
            ])

        content_widget.update("\n".join(lines))
