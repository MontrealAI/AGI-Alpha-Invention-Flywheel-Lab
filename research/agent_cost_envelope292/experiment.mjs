export function compare(network, front, request) {
  if (!network || !Array.isArray(network.tools)) throw Error("NETWORK_FORMAT");
  const a = network.tools.filter(t => t.name === front);
  if (a.length !== 1) throw Error("FRONT_AGENT");
  const f = a[0], parts = [f.instructions, f.command].filter(Boolean).map(s => s.trim());
  const system = parts.join("\n\n") || "You are a helpful agent.";
  const codeUnits = s => Array.from(s).reduce((n,c)=>n+(c.codePointAt(0)>65535?2:1),0);
  const req = request.length, sys = system.length;
  const shown = Math.round((req+300)/4)*2, proxy = Math.round((sys+req)/4);
  const independentShown = 2*Math.floor((codeUnits(request)+302)/4);
  const independentProxy = Math.floor((codeUnits(system)+codeUnits(request)+2)/4);
  if (req!==codeUnits(request)||sys!==codeUnits(system)||shown!==independentShown||proxy!==independentProxy) throw Error("INDEPENDENT_MISMATCH");
  return {front, agents:network.tools.length, request_utf16:req, system_utf16:sys, displayed_estimated_tokens:shown, illustrative_input_proxy_tokens:proxy, proxy_exceeds_display:proxy>shown};
}
