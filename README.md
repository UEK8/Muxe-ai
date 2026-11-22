
# Muxe AI: AI without internet

**The idea:** Free Facebook (zero-rated, "0") works even with no data balance, and it lets you view and post text. The app uses this to talk to AI.

### Components

- **The app (on your phone):** a chat interface. It only talks to Facebook and never connects to any AI directly.
- **Python bot (on a server or computer with real internet):** this is the "brain". It watches the post and replies.

### How they work together

1. You type a message in the app.
2. The app logs in to Facebook with your account and posts it as a **comment** on the post, with a number in front depending on the model.
3. The Python bot sees the new comment and decides what to do:
   - **Text:** answered by DeepSeek. If it starts with `2`, Gemini answers instead.
   - **Image:** read with Google Lens, then answered based on what is in it.
   - **`3` + description:** generates an image.
   - **"Who are you?":** replies "I am Muxe AI".
4. The bot posts the answer as a **reply** under your comment.
5. The app keeps refreshing until it finds the new reply, then shows it in the chat as a normal bubble.

### Why does it work without internet?

Real internet is only used by the bot. You only view and post text on free Facebook, and the bot does the rest.

### Limitations

The free plan usually allows text only (the notice says "view and post text"). Images and image generation may require a data balance. This has not been tested.



<img width="1280" height="661" alt="20261122_184826" src="https://github.com/user-attachments/assets/3a1c2121-06f6-4517-976b-6f36e7d5938b" />

