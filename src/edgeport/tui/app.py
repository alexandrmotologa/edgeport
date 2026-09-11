"""Textual live inspector application for EdgePort."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, ListView, Static

from edgeport.client.replay import ReplayEngine
from edgeport.client.storage import CapturedTransaction, TransactionStore
from edgeport.client.tunnel_client import TunnelClient

from .views import TransactionDetailView, TransactionItem


class EdgePortTUI(App):
    """Interactive terminal dashboard inspecting reverse tunnel traffic."""

    CSS = """
    Screen {
        layout: vertical;
        background: $surface;
    }
    #top-bar {
        height: 3;
        background: $panel;
        padding: 0 1;
        border-bottom: solid $primary;
    }
    #main-container {
        height: 1fr;
    }
    #left-pane {
        width: 45%;
        border-right: solid $primary;
        height: 1fr;
    }
    #right-pane {
        width: 55%;
        height: 1fr;
        padding: 1;
    }
    ListView {
        height: 1fr;
    }
    ListItem {
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "replay", "Replay", show=True),
        Binding("c", "copy_curl", "Copy cURL", show=True),
        Binding("e", "export", "Export HAR", show=True),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(
        self,
        client: TunnelClient,
        replay_engine: ReplayEngine | None = None,
        store: TransactionStore | None = None,
    ) -> None:
        super().__init__()
        self.client = client
        self.store = store if store is not None else client.store
        self.replay_engine = (
            replay_engine
            if replay_engine is not None
            else ReplayEngine(client.forwarder, self.store)
        )
        self._selected_txn: CapturedTransaction | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="top-bar"):
            yield Static(self._get_status_text(), id="status-banner")
        with Horizontal(id="main-container"):
            with Vertical(id="left-pane"):
                yield ListView(id="transaction-list")
            with Vertical(id="right-pane"):
                yield TransactionDetailView()
        yield Footer()

    def on_mount(self) -> None:
        self.title = "EdgePort Inspector"
        self.store.subscribe(self._on_new_transaction)
        self.client.on_connected(self._on_client_connected)
        self.client.on_disconnected(self._on_client_disconnected)

    def _get_status_text(self) -> str:
        url = self.client.public_url or "Connecting..."
        return (
            f"[bold cyan]Public URL:[/] {url}  "
            f"[bold green]Target:[/] {self.client.target_url}  "
            f"[bold yellow]Subdomain:[/] {self.client.subdomain}"
        )

    def _on_client_connected(self, public_url: str) -> None:
        banner = self.query_one("#status-banner", Static)
        banner.update(self._get_status_text())
        self.notify(f"Tunnel online: {public_url}", title="Connected")

    def _on_client_disconnected(self) -> None:
        banner = self.query_one("#status-banner", Static)
        banner.update("[bold red]Tunnel Disconnected - Reconnecting...[/]")

    def _on_new_transaction(self, txn: CapturedTransaction) -> None:
        self.call_from_thread(self._add_transaction_to_ui, txn)

    def _add_transaction_to_ui(self, txn: CapturedTransaction) -> None:
        txn_list = self.query_one("#transaction-list", ListView)
        txn_list.append(TransactionItem(txn))
        if len(txn_list) == 1:
            txn_list.index = 0
            self._update_selected_transaction(txn)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, TransactionItem):
            self._update_selected_transaction(event.item.transaction)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if isinstance(event.item, TransactionItem):
            self._update_selected_transaction(event.item.transaction)

    def _update_selected_transaction(self, txn: CapturedTransaction) -> None:
        self._selected_txn = txn
        detail_view = self.query_one(TransactionDetailView)
        detail_view.update_transaction(txn)

    async def action_replay(self) -> None:
        if not self._selected_txn:
            self.notify("No request selected to replay", severity="warning")
            return

        self.notify(f"Replaying {self._selected_txn.path}...", title="Replay")
        try:
            result = await self.replay_engine.replay(self._selected_txn.id)
            status_text = f"Replay status: {result.new_status}"
            self.notify(status_text, title="Replay Complete")
        except Exception as exc:
            self.notify(f"Replay failed: {exc}", severity="error")

    def action_copy_curl(self) -> None:
        if not self._selected_txn:
            self.notify("No request selected to copy", severity="warning")
            return

        curl_cmd = self._selected_txn.to_curl(self.client.target_url)
        # Attempt system clipboard copy
        try:
            import subprocess
            subprocess.run("clip", input=curl_cmd.encode("utf-8"), check=False)
            self.notify("Copied cURL command to clipboard", title="Clipboard")
        except Exception:
            self.notify(f"cURL: {curl_cmd[:60]}...", title="cURL Command")

    def action_export(self) -> None:
        from edgeport.client.exporter import save_har_file
        txns = self.store.all()
        if not txns:
            self.notify("No transactions to export", severity="warning")
            return
        base_url = self.client.public_url or self.client.target_url
        path = save_har_file(txns, "edgeport-traffic.har", base_url=base_url)
        self.notify(f"Exported {len(txns)} requests to {path.name}", title="Export Complete")

