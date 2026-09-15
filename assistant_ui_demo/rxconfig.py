import reflex as rx

config = rx.Config(
    app_name="assistant_ui_demo",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(appearance="inherit", accent_color="violet", radius="large"),
        ),
    ],
)
