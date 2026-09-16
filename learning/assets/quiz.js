/*
 * Shared quiz + task widgets for the DynaMem course.
 *
 * Multiple choice:
 *   <div class="quiz" data-answer="b" data-explain="Why b is right.">
 *     <p class="q">Question text?</p>
 *     <div class="opts">
 *       <button class="opt" data-key="a">...</button>
 *       <button class="opt" data-key="b">...</button>
 *     </div>
 *   </div>
 *   Options are shuffled on load so position never leaks the answer.
 *   Feedback is immediate; one attempt per question.
 *
 * Free-answer task:
 *   <div class="task" data-answer="8|eight" data-explain="Where it lives.">
 *     <p class="q">Prompt</p>
 *     <form><input name="a" autocomplete="off"><button>Check</button></form>
 *   </div>
 *   Accepted answers are separated by "|", compared case-insensitively after trimming.
 *
 * Score line (optional):  <p class="score" data-quiz-score></p>
 */
(function () {
  function shuffle(nodes) {
    for (let i = nodes.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [nodes[i], nodes[j]] = [nodes[j], nodes[i]];
    }
    return nodes;
  }

  const state = { total: 0, correct: 0, answered: 0 };

  function updateScore() {
    document.querySelectorAll("[data-quiz-score]").forEach((el) => {
      if (state.answered === 0) { el.textContent = ""; return; }
      el.textContent = `Score: ${state.correct} / ${state.answered} answered (${state.total} total)`;
    });
  }

  function feedbackEl(container) {
    let fb = container.querySelector(".fb");
    if (!fb) { fb = document.createElement("p"); fb.className = "fb"; container.appendChild(fb); }
    return fb;
  }

  function initQuiz(quiz) {
    const answer = (quiz.dataset.answer || "").trim();
    const explain = quiz.dataset.explain || "";
    const opts = quiz.querySelector(".opts");
    if (!opts) return;
    state.total += 1;

    shuffle(Array.from(opts.querySelectorAll("button.opt"))).forEach((b) => opts.appendChild(b));

    opts.addEventListener("click", (e) => {
      const btn = e.target.closest("button.opt");
      if (!btn || btn.disabled) return;
      const chosen = (btn.dataset.key || "").trim();
      const buttons = Array.from(opts.querySelectorAll("button.opt"));
      buttons.forEach((b) => { b.disabled = true; });
      const fb = feedbackEl(quiz);
      state.answered += 1;
      if (chosen === answer) {
        btn.classList.add("correct");
        state.correct += 1;
        fb.className = "fb ok";
        fb.textContent = "Correct. " + explain;
      } else {
        btn.classList.add("wrong");
        buttons.find((b) => (b.dataset.key || "").trim() === answer)?.classList.add("correct");
        fb.className = "fb bad";
        fb.textContent = "Not quite. " + explain;
      }
      updateScore();
    });
  }

  function initTask(task) {
    const accepted = (task.dataset.answer || "").split("|").map((s) => s.trim().toLowerCase()).filter(Boolean);
    const explain = task.dataset.explain || "";
    const form = task.querySelector("form");
    if (!form) return;
    state.total += 1;
    let done = false;
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const input = form.querySelector("input");
      const val = (input.value || "").trim().toLowerCase();
      const fb = feedbackEl(task);
      if (!val) { fb.className = "fb"; fb.textContent = "Type an answer first."; return; }
      const ok = accepted.includes(val);
      if (!done) { state.answered += 1; if (ok) state.correct += 1; }
      if (ok) {
        done = true;
        input.disabled = true;
        form.querySelector("button").disabled = true;
        fb.className = "fb ok";
        fb.textContent = "Correct. " + explain;
      } else {
        fb.className = "fb bad";
        fb.textContent = done ? "Already solved." : "Not it. Look again, then retry.";
      }
      updateScore();
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".quiz").forEach(initQuiz);
    document.querySelectorAll(".task").forEach(initTask);
    updateScore();
  });
})();
