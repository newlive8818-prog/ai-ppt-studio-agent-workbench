const OPENAI_FORM_METHOD = "openai/form";
const CANCELLED_NOTIFICATION_METHOD = "notifications/cancelled";

function isRequestId(value) {
  return typeof value === "string" || typeof value === "number";
}

function isOpenAIFormRequest(message) {
  return (
    message?.jsonrpc === "2.0" &&
    message?.method === OPENAI_FORM_METHOD &&
    isRequestId(message?.id)
  );
}

function cancellationRequestId(message) {
  if (
    message?.jsonrpc !== "2.0" ||
    message?.method !== CANCELLED_NOTIFICATION_METHOD
  ) {
    return null;
  }
  const requestId = message?.params?.requestId;
  return isRequestId(requestId) ? requestId : null;
}

class OpenAIFormCompatibleTransport {
  constructor(inner) {
    this.inner = inner;
    this.pendingOpenAIFormRequestIds = new Set();
    this.messageHandler = undefined;
    this.closeHandler = undefined;
    this.errorHandler = undefined;
  }

  get sessionId() {
    return this.inner.sessionId;
  }

  get onmessage() {
    return this.messageHandler;
  }

  set onmessage(handler) {
    this.messageHandler = handler;
    this.inner.onmessage = (message, extra) => {
      this.messageHandler?.(this.normalizeIncoming(message), extra);
    };
  }

  get onclose() {
    return this.closeHandler;
  }

  set onclose(handler) {
    this.closeHandler = handler;
    this.inner.onclose = () => {
      this.pendingOpenAIFormRequestIds.clear();
      this.closeHandler?.();
    };
  }

  get onerror() {
    return this.errorHandler;
  }

  set onerror(handler) {
    this.errorHandler = handler;
    this.inner.onerror = (error) => {
      this.errorHandler?.(error);
    };
  }

  async start() {
    await this.inner.start();
  }

  async send(message, options) {
    const trackedId = isOpenAIFormRequest(message) ? message.id : null;
    if (trackedId !== null) {
      this.pendingOpenAIFormRequestIds.add(trackedId);
    }
    const cancelledId = cancellationRequestId(message);
    if (cancelledId !== null) {
      this.pendingOpenAIFormRequestIds.delete(cancelledId);
    }
    try {
      await this.inner.send(message, options);
    } catch (error) {
      if (trackedId !== null) {
        this.pendingOpenAIFormRequestIds.delete(trackedId);
      }
      throw error;
    }
  }

  async close() {
    this.pendingOpenAIFormRequestIds.clear();
    await this.inner.close();
  }

  setProtocolVersion(version) {
    this.inner.setProtocolVersion?.(version);
  }

  normalizeIncoming(message) {
    const requestId = message?.id;
    if (
      !isRequestId(requestId) ||
      !this.pendingOpenAIFormRequestIds.has(requestId)
    ) {
      return message;
    }
    const isResult = Object.hasOwn(message, "result");
    const isError = Object.hasOwn(message, "error");
    if (!isResult && !isError) {
      return message;
    }
    this.pendingOpenAIFormRequestIds.delete(requestId);
    if (
      !isResult ||
      message.result === null ||
      typeof message.result !== "object" ||
      Array.isArray(message.result) ||
      message.result._meta !== null
    ) {
      return message;
    }
    const result = { ...message.result };
    delete result._meta;
    return { ...message, result };
  }
}

export function createOpenAIFormCompatibleTransport(inner) {
  return new OpenAIFormCompatibleTransport(inner);
}
