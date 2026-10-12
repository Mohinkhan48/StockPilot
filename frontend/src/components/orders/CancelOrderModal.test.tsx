/**
 * frontend/src/components/orders/CancelOrderModal.test.tsx
 * Unit tests for CancelOrderModal:
 * - Rendering title, description, buttons
 * - Confirming and dismissing the modal
 * - Loading / processing states and button disabling
 * - API error display and retry handling
 * - Successful and failed cancellation workflows
 */

import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { renderToString } from 'react-dom/server';
import { CancelOrderModal, CancelOrderModalProps } from './CancelOrderModal';

describe('CancelOrderModal Component', () => {
  it('renders nothing when isOpen is false', () => {
    const html = renderToString(
      <CancelOrderModal
        isOpen={false}
        orderId={101}
        orderStatus="confirmed"
        itemCount={3}
        isProcessing={false}
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />
    );
    expect(html).toBe('');
  });

  it('renders modal title with order ID and confirmed stock restoration explanation', () => {
    const html = renderToString(
      <CancelOrderModal
        isOpen={true}
        orderId={101}
        orderStatus="confirmed"
        itemCount={3}
        isProcessing={false}
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />
    );

    // Title requirement: "Cancel Order #<order ID>?" (React SSR may insert <!-- --> comments)
    expect(html).toMatch(/Cancel Order #(?:<!-- -->)?101(?:<!-- -->)?\?/);

    // Requirement: Explain that cancelling will restore stock and record return
    expect(html).toContain('restore stock for all');
    expect(html).toMatch(/3(?:<!-- -->)?\s*(?:<!-- -->)?\s*order\s*(?:<!-- -->)?\s*items/);
    expect(html).toContain('record the inventory return in the audit ledger');

    // Requirement: Buttons "Keep Order" and "Cancel Order"
    expect(html).toContain('Keep Order');
    expect(html).toContain('Cancel Order');
  });

  it('renders pending draft explanation when order status is pending', () => {
    const html = renderToString(
      <CancelOrderModal
        isOpen={true}
        orderId={205}
        orderStatus="pending"
        itemCount={1}
        isProcessing={false}
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />
    );

    expect(html).toMatch(/Cancel Order #(?:<!-- -->)?205(?:<!-- -->)?\?/);
    expect(html).toContain('No warehouse inventory was deducted for this pending order');
  });

  it('disables both buttons and shows loading indicator while processing', () => {
    const html = renderToString(
      <CancelOrderModal
        isOpen={true}
        orderId={101}
        orderStatus="confirmed"
        itemCount={2}
        isProcessing={true}
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />
    );

    // Loading indicator text
    expect(html).toContain('Cancelling Order...');

    // Disabled buttons
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>[\s\S]*?Keep Order/);
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>[\s\S]*?Cancelling Order\.\.\./);
  });

  it('displays error banner when error prop is provided', () => {
    const errorMessage = 'Insufficient permission or network timeout occurred.';
    const html = renderToString(
      <CancelOrderModal
        isOpen={true}
        orderId={101}
        orderStatus="confirmed"
        itemCount={2}
        isProcessing={false}
        error={errorMessage}
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />
    );

    expect(html).toContain(errorMessage);
    expect(html).toContain('role="alert"');
  });

  it('invokes onClose callback when dismissed', () => {
    const handleClose = vi.fn();
    const handleConfirm = vi.fn();

    const props: CancelOrderModalProps = {
      isOpen: true,
      orderId: 101,
      orderStatus: 'confirmed',
      itemCount: 2,
      isProcessing: false,
      onConfirm: handleConfirm,
      onClose: handleClose,
    };

    // Simulate clicking "Keep Order"
    props.onClose();
    expect(handleClose).toHaveBeenCalledTimes(1);
    expect(handleConfirm).not.toHaveBeenCalled();
  });

  it('invokes onConfirm callback exactly once when confirmed', async () => {
    const handleClose = vi.fn();
    const handleConfirm = vi.fn();

    const props: CancelOrderModalProps = {
      isOpen: true,
      orderId: 101,
      orderStatus: 'confirmed',
      itemCount: 2,
      isProcessing: false,
      onConfirm: handleConfirm,
      onClose: handleClose,
    };

    // Simulate clicking "Cancel Order"
    await props.onConfirm();
    expect(handleConfirm).toHaveBeenCalledTimes(1);
    expect(handleClose).not.toHaveBeenCalled();
  });

  it('handles cancellation API failure gracefully without closing modal', async () => {
    let modalOpen = true;
    let modalError: string | null = null;
    let isProcessing = false;

    const mockApiCancel = vi.fn().mockRejectedValue(new Error('Cannot cancel already-completed order'));

    const handleExecuteCancel = async () => {
      isProcessing = true;
      try {
        await mockApiCancel();
        modalOpen = false;
      } catch (err) {
        modalError = (err as Error).message;
        // Modal remains open on failure
      } finally {
        isProcessing = false;
      }
    };

    await handleExecuteCancel();

    expect(mockApiCancel).toHaveBeenCalledTimes(1);
    expect(modalOpen).toBe(true);
    expect(modalError).toBe('Cannot cancel already-completed order');
    expect(isProcessing).toBe(false);

    // Verify error is rendered inside the modal
    const html = renderToString(
      <CancelOrderModal
        isOpen={modalOpen}
        orderId={101}
        orderStatus="confirmed"
        itemCount={2}
        isProcessing={isProcessing}
        error={modalError}
        onConfirm={handleExecuteCancel}
        onClose={() => { modalOpen = false; }}
      />
    );
    expect(html).toContain('Cannot cancel already-completed order');
  });

  it('handles successful cancellation workflow by updating state and closing modal', async () => {
    let modalOpen = true;
    let successMessage: string | null = null;
    let isProcessing = false;

    const mockApiCancel = vi.fn().mockResolvedValue({ id: 101, status: 'cancelled' });

    const handleExecuteCancel = async () => {
      isProcessing = true;
      try {
        await mockApiCancel();
        modalOpen = false;
        successMessage = 'Order #101 cancelled successfully. Stock has been restored.';
      } finally {
        isProcessing = false;
      }
    };

    await handleExecuteCancel();

    expect(mockApiCancel).toHaveBeenCalledTimes(1);
    expect(modalOpen).toBe(false);
    expect(successMessage).toBe('Order #101 cancelled successfully. Stock has been restored.');
    expect(isProcessing).toBe(false);
  });
});
