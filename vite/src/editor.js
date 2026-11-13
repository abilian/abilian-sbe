/* Rich text for forum posts, on the pages whose forms have the widget
 * (widgets/richtext.html). The textarea stays the form field: the editor replaces
 * it on screen and writes its HTML back to it. The server sanitises that HTML.
 */
import { Editor } from "@tiptap/core";
import Image from "@tiptap/extension-image";
import StarterKit from "@tiptap/starter-kit";

function linkTo(editor, href) {
  const chain = editor.chain().focus().extendMarkRange("link");
  if (!href) {
    chain.unsetLink().run();
  } else if (editor.state.selection.empty && !editor.isActive("link")) {
    // Nothing selected to turn into a link, so the address is its own text.
    const marks = [{ type: "link", attrs: { href } }];
    chain.insertContent({ type: "text", text: href, marks }).run();
  } else {
    chain.setLink({ href }).run();
  }
}

function runTool(editor, button) {
  const { command, level, linkPrompt } = button.dataset;
  if (linkPrompt) {
    const current = editor.getAttributes("link").href ?? "";
    const href = window.prompt(linkPrompt, current);
    if (href !== null) linkTo(editor, href.trim());
  } else if (level) {
    editor.chain().focus()[command]({ level: Number(level) }).run();
  } else {
    editor.chain().focus()[command]().run();
  }
}

function showActiveTools(editor, buttons) {
  for (const button of buttons) {
    const { active, level } = button.dataset;
    if (active) {
      const attrs = level ? { level: Number(level) } : {};
      button.setAttribute("aria-pressed", editor.isActive(active, attrs));
    }
  }
}

function mount(textarea) {
  const root = textarea.nextElementSibling;
  const buttons = [...root.querySelectorAll("button")];

  const editor = new Editor({
    element: root.querySelector(".richtext-content"),
    // Only what the sanitiser keeps (ALLOWED_TAGS in forum/forms.py), so nothing
    // offered here vanishes on save. Image has no button, since the CSP blocks
    // images from other sites, but old posts have to survive being edited.
    extensions: [
      StarterKit.configure({
        codeBlock: false,
        horizontalRule: false,
        strike: false,
        // It keeps an empty paragraph after every list, heading and quote, and
        // those would be saved as blank lines in the post.
        trailingNode: false,
        link: { openOnClick: false },
      }),
      Image,
    ],
    content: textarea.value,
    editorProps: {
      attributes: {
        role: "textbox",
        "aria-multiline": "true",
        "aria-label": textarea.getAttribute("aria-label"),
      },
    },
    // An empty document is "<p></p>", which would satisfy the required validator.
    onUpdate: () => {
      textarea.value = editor.isEmpty ? "" : editor.getHTML();
    },
    onTransaction: () => showActiveTools(editor, buttons),
  });

  // A button taking the focus would leave the editor until its next frame, and
  // whatever is typed by then lands outside the list or quote just started.
  root
    .querySelector(".richtext-toolbar")
    .addEventListener("mousedown", (event) => event.preventDefault());

  for (const button of buttons) {
    button.addEventListener("click", () => runTool(editor, button));
  }
  showActiveTools(editor, buttons);

  textarea.hidden = true;
  root.hidden = false;
}

document.querySelectorAll("textarea[data-richtext]").forEach(mount);
