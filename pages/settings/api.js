export function createApi(bridge) {
  const apiGet = bridge?.apiGet?.bind(bridge);
  const apiPost = bridge?.apiPost?.bind(bridge);

  if (!apiGet || !apiPost) {
    throw new Error("Bridge API is unavailable");
  }

  function unwrapBridgeResponse(response) {
    if (
      response &&
      typeof response === "object" &&
      Object.prototype.hasOwnProperty.call(response, "ok")
    ) {
      if (!response.ok) {
        throw new Error(response.message || "Request failed");
      }
      return Object.prototype.hasOwnProperty.call(response, "data")
        ? response.data
        : response;
    }
    return response;
  }

  async function safeGet(endpoint, params) {
    const response = await apiGet(endpoint, params);
    return unwrapBridgeResponse(response);
  }

  async function safePost(endpoint, body) {
    const response = await apiPost(endpoint, body);
    return unwrapBridgeResponse(response);
  }

  return {
    safeGet,
    safePost,
  };
}
