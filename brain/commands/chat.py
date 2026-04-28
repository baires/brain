from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Footer, Input, LoadingIndicator, Markdown, Static

from brain.config import BrainConfig
from brain.ollama import OllamaClient
from brain.prompts import ANSWER_INSTRUCTIONS
from brain.query import QueryEngine
from brain.store import BrainStore


def _build_chat_prompt(
    user_message: str,
    context: str,
    history: list[tuple[str, str]],
) -> str:
    lines = []
    if context:
        lines.append(f"Context:\n{context}\n")
        lines.append(f"{ANSWER_INSTRUCTIONS}\n")
    if history:
        lines.append("Conversation:")
        for role, content in history:
            lines.append(f"{role}: {content}")
        lines.append("")
    lines.append(f"User: {user_message}")
    lines.append("Assistant:")
    return "\n".join(lines)


class ChatApp(App):
    BINDINGS = [
        Binding("up", "scroll_up", "Scroll up", show=False),
        Binding("down", "scroll_down", "Scroll down", show=False),
        Binding("pageup", "scroll_page_up", "Page up", show=False),
        Binding("pagedown", "scroll_page_down", "Page down", show=False),
        Binding("home", "scroll_home", "Top", show=False),
        Binding("end", "scroll_end", "Bottom", show=False),
    ]

    CSS = """
    ChatApp {
        background: $surface-darken-1;
    }

    #chat-view {
        width: 100%;
        height: 1fr;
        padding: 0 1;
    }

    #chat-input {
        dock: bottom;
        height: auto;
        margin: 0 1 1 1;
    }

    .user-message {
        width: auto;
        max-width: 70%;
        height: auto;
        margin: 1 0 1 8;
        padding: 0 1;
        background: $success-darken-3;
        border: tall $success;
        color: $text;
        content-align: right middle;
        align: right middle;
    }

    .assistant-message {
        width: 100%;
        height: auto;
        margin: 1 0;
    }

    .thinking-indicator {
        width: 6;
        height: 1;
        margin: 1 0;
    }

    .system-message {
        width: 100%;
        height: auto;
        margin: 1 0;
        color: $warning;
        text-align: center;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        cfg = BrainConfig.load_from()
        self.cfg = cfg
        self.store = BrainStore(db_path=cfg.db_path)
        self.ollama = OllamaClient(base_url=cfg.ollama_url)
        self.engine = QueryEngine(
            store=self.store,
            ollama=self.ollama,
            embed_model=cfg.embed_model,
            chat_model=cfg.chat_model,
            fetch_k=cfg.retrieval_fetch_k,
            top_k=cfg.retrieval_top_k,
            mmr_lambda=cfg.retrieval_mmr_lambda,
            max_context_chars=cfg.retrieval_max_context_chars,
            max_best_distance=cfg.retrieval_max_best_distance,
            relative_distance_margin=cfg.retrieval_relative_distance_margin,
            system_prompt=cfg.agent.system_prompt,
            query_expansion=cfg.retrieval_query_expansion,
        )
        self.history: list[tuple[str, str]] = []
        self.rag_enabled = True
        self.max_history_turns = 10
        self.last_context = ""

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="chat-view")
        yield Input(placeholder="Message... (/help for commands)", id="chat-input")
        yield Footer()

    async def on_mount(self) -> None:
        self.title = "Brain Chat"
        self.sub_title = f"{self.cfg.chat_model} • {self.cfg.agent.tone}"
        await self._show_welcome()
        self.query_one("#chat-input", Input).focus()

    async def _show_welcome(self) -> None:
        welcome_text = (
            f"**Welcome to Brain Chat**  \n"
            f"Model: `{self.cfg.chat_model}`  \n"
            f"Tone: *{self.cfg.agent.tone}*  \n"
            f"Goals: *{self.cfg.agent.goals}*  \n\n"
            f"Type `/help` for commands."
        )
        await self._add_assistant_message(welcome_text)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        if not message:
            return

        input_widget = self.query_one("#chat-input", Input)
        input_widget.value = ""

        if message.startswith("/"):
            await self._handle_command(message)
            return

        await self._add_user_message(message)
        await self._process_message(message)

    async def _add_user_message(self, text: str) -> None:
        chat_view = self.query_one("#chat-view", VerticalScroll)
        static = Static(text, classes="user-message")
        await chat_view.mount(static)
        static.scroll_visible()

    async def _add_thinking_indicator(self) -> LoadingIndicator:
        chat_view = self.query_one("#chat-view", VerticalScroll)
        indicator = LoadingIndicator(classes="thinking-indicator")
        await chat_view.mount(indicator)
        indicator.scroll_visible()
        return indicator

    async def _add_assistant_message(self, text: str) -> Markdown:
        chat_view = self.query_one("#chat-view", VerticalScroll)
        md = Markdown(text, classes="assistant-message")
        await chat_view.mount(md)
        md.scroll_visible()
        return md

    async def _add_system_message(self, text: str) -> None:
        chat_view = self.query_one("#chat-view", VerticalScroll)
        static = Static(text, classes="system-message")
        await chat_view.mount(static)
        static.scroll_visible()

    async def _process_message(self, message: str) -> None:
        indicator = await self._add_thinking_indicator()

        context = ""
        if self.rag_enabled:
            try:
                import asyncio

                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(None, lambda: self.engine.retrieve(message))
                context = self.engine.build_context(results) if results else ""
                self.last_context = context
            except Exception as e:
                await self._add_system_message(f"RAG error: {e}")

        prompt = _build_chat_prompt(message, context, self.history)
        self._stream_response(prompt, indicator, message)

    @work(thread=True)
    def _stream_response(self, prompt: str, indicator: LoadingIndicator, message: str) -> None:
        response_parts: list[str] = []

        try:
            for token in self.ollama.chat(
                prompt=prompt,
                model=self.cfg.chat_model,
                system=self.cfg.agent.system_prompt,
            ):
                response_parts.append(token)
        except Exception as e:
            response_parts = [f"**Error:** {e}"]

        async def finalize() -> None:
            response_text = "".join(response_parts)
            self.history.append(("User", message))
            self.history.append(("Assistant", response_text))
            if len(self.history) > self.max_history_turns * 2:
                self.history = self.history[-self.max_history_turns * 2 :]
            chat_view = self.query_one("#chat-view", VerticalScroll)
            md = Markdown(response_text, classes="assistant-message")
            await indicator.remove()
            await chat_view.mount(md)
            chat_view.scroll_end(animate=False)

        self.call_from_thread(self.app.call_later, finalize)

    def action_scroll_up(self) -> None:
        self.query_one("#chat-view", VerticalScroll).scroll_up()

    def action_scroll_down(self) -> None:
        self.query_one("#chat-view", VerticalScroll).scroll_down()

    def action_scroll_page_up(self) -> None:
        self.query_one("#chat-view", VerticalScroll).scroll_page_up()

    def action_scroll_page_down(self) -> None:
        self.query_one("#chat-view", VerticalScroll).scroll_page_down()

    def action_scroll_home(self) -> None:
        self.query_one("#chat-view", VerticalScroll).scroll_home()

    def action_scroll_end(self) -> None:
        self.query_one("#chat-view", VerticalScroll).scroll_end()

    async def _handle_command(self, message: str) -> None:
        cmd = message[1:].lower().strip()
        if cmd in ("quit", "exit", "q"):
            self.exit()
        elif cmd == "clear":
            chat_view = self.query_one("#chat-view", VerticalScroll)
            await chat_view.remove_children()
            await self._show_welcome()
        elif cmd == "rag on":
            self.rag_enabled = True
            await self._add_system_message("📚 RAG enabled")
        elif cmd == "rag off":
            self.rag_enabled = False
            await self._add_system_message("📚 RAG disabled")
        elif cmd == "context":
            await self._add_assistant_message(
                self.last_context or "_No context retrieved for the last answer._"
            )
        elif cmd == "help":
            help_text = (
                "**Commands:**  \n"
                "`/quit` — Exit chat  \n"
                "`/clear` — Clear history  \n"
                "`/rag on` — Enable document retrieval  \n"
                "`/rag off` — Disable document retrieval  \n"
                "`/context` — Show last retrieved citations  \n"
                "`/help` — Show this help"
            )
            await self._add_assistant_message(help_text)
        else:
            await self._add_system_message(f"❓ Unknown command: `{message}`")


def run_chat() -> None:
    app = ChatApp()
    app.run()
