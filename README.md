<p align="center">
  <img src="https://i.supaimg.com/af2484ff-b3c4-4b44-8b12-dbd98b1bdd57/4e1a7307-e87b-43cf-9685-c6bd31406fdc.jpg" alt="Banner" width="40%" />
</p>

<hr />

<div style="font-family: Georgia, 'Times New Roman', Times, serif; line-height: 1.6;">

<h2>Muxe AI: AI without internet</h2>

<p><b>The idea:</b> Free Facebook (zero-rated, "0") works even with no data balance, and it lets you view and post text. The app uses this to talk to AI.</p>

<h3>Components</h3>

<ul>
  <li><b>The app (on your phone):</b> a chat interface. It only talks to Facebook and never connects to any AI directly.</li>
  <li><b>Python bot (on a server or computer with real internet):</b> this is the "brain". It watches the post and replies.</li>
</ul>

<h3>How they work together</h3>

<ol>
  <li>You type a message in the app.</li>
  <li>The app logs in to Facebook with your account and posts it as a comment on the post, with a number in front depending on the model.</li>
  <li>The Python bot sees the new comment and decides what to do:
    <ul>
      <li><b>Text:</b> answered by DeepSeek. If it starts with <code>2</code>, Gemini answers instead.</li>
      <li><b>Image:</b> read with Google Lens, then answered based on what is in it.</li>
      <li><b><code>3</code> + description:</b> generates an image.</li>
      <li><b>"Who are you?":</b> replies "I am Muxe AI".</li>
    </ul>
  </li>
  <li>The bot posts the answer as a reply under your comment.</li>
  <li>The app keeps refreshing until it finds the new reply, then shows it in the chat as a normal bubble.</li>
</ol>

<h3>Why does it work without internet?</h3>

<p>Real internet is only used by the bot. You only view and post text on free Facebook, and the bot does the rest.</p>

<h3>Limitations</h3>

<p>The free plan usually allows text only (the notice says "view and post text"). Images and image generation may require a data balance. This has not been tested.</p>

</div>

<hr />

<p align="center">
  <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/javascript/javascript-original.svg" alt="JavaScript" width="40" />
  <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/python/python-original.svg" alt="Python" width="40" />
  <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/java/java-original.svg" alt="Java" width="40" />
  <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/html5/html5-original.svg" alt="HTML5" width="40" />
</p>
