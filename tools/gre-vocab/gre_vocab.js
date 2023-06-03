import { words } from "./words.js"

const question = document.querySelector(".question");
let choices = [];
let num_choices = document.querySelector(".num-choices")
let num_chances = document.querySelector(".num-chances")
const button_next = document.querySelector(".next-question");
const scoreboard = document.querySelector(".scoreboard");
const remaining = document.querySelector(".remaining");

var correct_answer = {};
var score = { correct: 0, incorrect: 0 };
var chances = { current: 0, max: Number(num_chances.value) };
var previous_answers = [];

makeChoiceButtons(num_choices.value);
newQuestion();
updateScore();

function makeChoiceButtons(num_choices) {
  if (choices) {
    deleteOldChoices();
  }
  const answer_section = document.querySelector(".choices");
  for (let i = 0; i < num_choices; i++) {
    const choice = document.createElement("button");
    choice.classList.add("choice")
    question.insertAdjacentElement("afterend", choice)
    choices.push(choice)
  }
  addAnswerListeners();
}

function deleteOldChoices() {
  choices.forEach(choice => choice.remove());
  choices = [];
}

function randomItem(array, replacement=true) {
  let randomIndex = Math.floor(Math.random() * array.length);
  let randomItem = array[randomIndex]
  if (!replacement) {
    array.splice(randomIndex, 1)
  }
  return randomItem
}

// https://stackoverflow.com/questions/2450954/how-to-randomize-shuffle-a-javascript-array
function shuffle(array) {
  let currentIndex = array.length,  randomIndex;

  // While there remain elements to shuffle.
  while (currentIndex != 0) {

    // Pick a remaining element.
    randomIndex = Math.floor(Math.random() * currentIndex);
    currentIndex--;

    // And swap it with the current element.
    [array[currentIndex], array[randomIndex]] = [
      array[randomIndex], array[currentIndex]];
  }

  return array;
}

function newQuestion() {
  clearColors(choices)
  chances.current = 0
  let new_answer = randomItem(words, false) // draw without replacement

  let options = [new_answer.Definition]
  while (options.length < num_choices.value) {
    let item = randomItem(words).Definition
    if (!(options.includes(item))) {
      options.push(item)
    }
  }

  setQuestion(new_answer)

  shuffle(options)
  for (let i = 0; i < num_choices.value; i++) {
    const text = options[i];
    const element = choices[i];
    element.innerHTML = text;
  }
}

function setQuestion(word) {
  question.innerHTML = word.Word;
  correct_answer = word
}

function checkAnswer(answer) {
  if (chances.current >= chances.max) return;
  let correct = correct_answer.Definition === answer.innerHTML
  if (correct) {
    answer.classList.add("correct")
    score.correct++
    chances.current = chances.max
    setTimeout(newQuestion, 1000);
  } else {
    answer.classList.add("incorrect")
    score.incorrect++
    chances.current++
    words.push(correct_answer) // add word back to stack
  }
  previous_answers.push({"Word": correct_answer.Word, "Answer": answer.innerHTML, "Correct": correct})
  updateScore()
  console.log(chances)
  if (chances.current === chances.max) {
    highlightCorrect()
  }
}

function clearColors(elements) {
  elements.forEach((element) => element.classList.remove('correct', 'incorrect'))
}

function updateScore() {
  scoreboard.innerHTML = score.correct + "/" + (score.correct + score.incorrect)
  remaining.innerHTML = words.length + " remaining"
}

function showPreviousAnswers() {
  window.alert(JSON.stringify(previous_answers))
}

function highlightCorrect() {
  choices.forEach((choice => {
    if (choice.innerHTML === correct_answer.Definition) {
      choice.classList.add("correct")
      return
    }
  }))
}

function addAnswerListeners() {
  choices.forEach((choice => {
    choice.addEventListener("click", () => checkAnswer(choice));
  }))
}

button_next.addEventListener("click", () => {
  newQuestion()
});

num_choices.addEventListener("change", () => {
  makeChoiceButtons(num_choices.value);
  newQuestion();
})

num_chances.addEventListener("change", () => {
  chances["max"] = Number(num_chances.value);
})

scoreboard.addEventListener("click", () => {
  showPreviousAnswers()
})
