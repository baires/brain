from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Input, LoadingIndicator, Markdown, Static

from brain.config import BrainConfig
from brain.prompts import ANSWER_INSTRUCTIONS
from brain.providers import get_provider
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
        background: #11130f;
        color: #d7d0c0;
    }

    #masthead {
        dock: top;
        height: 4;
        padding: 1 2 0 2;
        background: #181b16;
        border-bottom: solid #4f584a;
    }

    #brand {
        width: 1fr;
        content-align: left middle;
        text-style: bold;
        color: #f2eadb;
    }

    .status-pill {
        width: auto;
        min-width: 18;
        height: 1;
        margin: 0 0 0 1;
        padding: 0 1;
        background: #242920;
        color: #c9c3b5;
        text-align: center;
        content-align: center middle;
    }

    #chat-view {
        width: 100%;
        height: 1fr;
        padding: 1 3 2 3;
        background: #11130f;
        scrollbar-color: #7ab8b0;
        scrollbar-color-hover: #97d5cb;
    }

    #chat-input-deck {
        dock: bottom;
        width: 100%;
        height: 6;
        padding: 1 2 1 2;
        background: #11130f;
        border-top: solid #30362d;
    }

    #chat-input {
        width: 1fr;
        height: 3;
        margin: 0;
        border: solid #4f584a;
        background: #181b16;
        color: #f2eadb;
    }

    #chat-input:focus {
        border: solid #7ea6d8;
    }

    .user-message {
        width: 100%;
        height: auto;
        margin: 2 0 1 0;
        padding: 0 1;
        color: #b0ca89;
        text-align: right;
    }

    .assistant-message {
        width: 100%;
        height: auto;
        margin: 1 0 2 0;
        padding: 0 1 0 0;
        color: #d7d0c0;
    }

    .assistant-message MarkdownH1,
    .assistant-message MarkdownH2,
    .assistant-message MarkdownH3 {
        color: #f2eadb;
        text-style: bold;
    }

    .assistant-message MarkdownBullet {
        color: #7ab8b0;
    }

    .assistant-message MarkdownCode {
        color: #edc978;
    }

    .welcome-message {
        width: 100%;
        height: auto;
        margin: 0 0 2 0;
        padding: 1 2;
        border: solid #4f584a;
        background: #181b16;
        color: #d7d0c0;
    }

    .thinking-indicator {
        width: 12;
        height: 3;
        margin: 1 0 2 0;
        padding: 0 1;
        border: solid #7ea6d8;
        background: #181b16;
    }

    .system-message {
        width: auto;
        height: auto;
        margin: 1 0 1 2;
        padding: 0 1;
        border-left: heavy #d4ad58;
        background: #242920;
        color: #edc978;
        text-align: center;
    }

    .success-message {
        border-left: heavy #8fad70;
        color: #b0ca89;
    }

    .error-message {
        border-left: heavy #d97c66;
        color: #f09a82;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        cfg = BrainConfig.load_from()
        self.cfg = cfg
        self.store = BrainStore(db_path=cfg.db_path)
        self.llm = get_provider(cfg)
        self.engine = QueryEngine(
            store=self.store,
            llm=self.llm,
            embedder=self.llm,
            embed_model=cfg.embed_model,
            chat_model=cfg.chat_model,
            fetch_k=cfg.retrieval_fetch_k,
            top_k=cfg.retrieval_top_k,
            mmr_lambda=cfg.retrieval_mmr_lambda,
            max_context_tokens=cfg.retrieval_max_context_tokens,
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
        with Horizontal(id="masthead"):
            yield Static("[#7ab8b0]brain[/#7ab8b0] chat", id="brand")
            yield Static("model pending", id="model-pill", classes="status-pill")
            yield Static("retrieval on", id="rag-pill", classes="status-pill")
        yield VerticalScroll(id="chat-view")
        with Horizontal(id="chat-input-deck"):
            yield Input(
                placeholder="Message your knowledge base...  /help for commands", id="chat-input"
            )

    async def on_mount(self) -> None:
        self.title = "Brain Chat"
        self.sub_title = f"{self.cfg.chat_model} | {self.cfg.agent.tone}"
        self.query_one("#model-pill", Static).update(f"model {self.cfg.chat_model}")
        self._sync_rag_status()
        await self._show_welcome()
        self.query_one("#chat-input", Input).focus()

    def _sync_rag_status(self) -> None:
        state = "on" if self.rag_enabled else "off"
        self.query_one("#rag-pill", Static).update(f"retrieval {state}")

    async def _show_welcome(self) -> None:
        welcome_text = (
            f"**Brain Chat is ready.**  \n"
            f"`{self.cfg.chat_model}` answers in a {self.cfg.agent.tone} tone.  \n"
            f"{self.cfg.agent.goals}  \n\n"
            f"`/help` shows commands. `/context` opens the last retrieved citations."
        )
        await self._add_assistant_message(welcome_text, classes="assistant-message welcome-message")

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
        static = Static(f"you > {text}", classes="user-message", markup=False)
        await chat_view.mount(static)
        static.scroll_visible()

    async def _add_thinking_indicator(self) -> LoadingIndicator:
        chat_view = self.query_one("#chat-view", VerticalScroll)
        indicator = LoadingIndicator(classes="thinking-indicator")
        await chat_view.mount(indicator)
        indicator.scroll_visible()
        return indicator

    async def _add_assistant_message(
        self, text: str, classes: str = "assistant-message"
    ) -> Markdown:
        chat_view = self.query_one("#chat-view", VerticalScroll)
        md = Markdown(text, classes=classes)
        await chat_view.mount(md)
        md.scroll_visible()
        return md

    async def _add_system_message(self, text: str, classes: str = "system-message") -> None:
        chat_view = self.query_one("#chat-view", VerticalScroll)
        static = Static(text, classes=classes, markup=False)
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
                await self._add_system_message(
                    f"RAG error: {e}", classes="system-message error-message"
                )

        prompt = _build_chat_prompt(message, context, self.history)
        self._stream_response(prompt, indicator, message)

    @work(thread=True)
    def _stream_response(self, prompt: str, indicator: LoadingIndicator, message: str) -> None:
        response_parts: list[str] = []

        try:
            for token in self.llm.chat(
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
            self._sync_rag_status()
            await self._add_system_message(
                "Retrieval enabled", classes="system-message success-message"
            )
        elif cmd == "rag off":
            self.rag_enabled = False
            self._sync_rag_status()
            await self._add_system_message("Retrieval disabled")
        elif cmd == "context":
            await self._add_assistant_message(
                self.last_context or "_No context retrieved for the last answer._"
            )
        elif cmd == "help":
            help_text = (
                "**Commands**  \n"
                "`/quit` - Exit chat  \n"
                "`/clear` - Clear the screen  \n"
                "`/rag on` - Enable document retrieval  \n"
                "`/rag off` - Disable document retrieval  \n"
                "`/context` - Show last retrieved citations  \n"
                "`/help` - Show this help"
            )
            await self._add_assistant_message(help_text)
        else:
            await self._add_system_message(
                f"Unknown command: {message}", classes="system-message error-message"
            )


def run_chat() -> None:
    app = ChatApp()
    app.run()
