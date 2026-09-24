export function mathParts(text: string) {
  return text.split(/([_^](?:\{[^{}]*\}|[A-Za-z0-9]+))/g).filter(Boolean).map(part => {
    const script = /^([_^])(?:\{([^{}]*)\}|([A-Za-z0-9]+))$/.exec(part);
    return script ? {text: script[2] ?? script[3]!, kind: script[1] === '_' ? 'sub' : 'sup'} : {text: part, kind: 'plain'};
  });
}
