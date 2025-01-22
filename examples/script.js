let ele = document.getElementById('my-b')
ele.onclick = () => alert("Thanks for clicking!")


let imgEle = document.createElement("img")
imgEle.src = "x"
imgEle.setAttribute("onerror", "console.log(1)")
divEle.appendChild(imgEle)

window.setTimeout(() => {console.log("Timeout done")}, 2)