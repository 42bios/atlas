function toolbar(placeholder,extra=''){return `<div class="list-toolbar"><label class="search-field">${icon('search',17)}<input id="search" placeholder="${placeholder}" value="${esc(query)}" aria-label="${placeholder}"></label>${extra}</div>`;}
function match(x){return !query||JSON.stringify(x).toLowerCase().includes(query.toLowerCase());}
