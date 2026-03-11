# Accessibility Testing Guide

## Manual Testing Checklist

### Keyboard Navigation Tests

#### 1. Tab Navigation
- [ ] **Open the app** (`/app`)
- [ ] **Press Tab repeatedly** to navigate through interactive elements
- [ ] **Verify focus order**: Chat input → VS Code button → other focusable elements
- [ ] **Check focus visibility**: Blue outline should be visible around focused elements
- [ ] **Test Tab key**: Should open command palette modal

#### 2. Button Activation
- [ ] **Focus on VS Code button**
- [ ] **Press Enter**: Should open VS Code modal
- [ ] **Press Space**: Should also activate button
- [ ] **Focus on scroll button** (when visible)
- [ ] **Press Enter/Space**: Should scroll to bottom

#### 3. Chat Input Controls
- [ ] **Focus chat input** (auto-focused on page load)
- [ ] **Type message** and press Enter: Should send message
- [ ] **Press Shift+Enter**: Should add new line
- [ ] **Press "/" when not focused on input**: Should focus input

#### 4. Modal Navigation
- [ ] **Open command palette** (Tab key)
- [ ] **Type search query**: Should show results
- [ ] **Use Arrow keys**: Should navigate through results
- [ ] **Press Enter**: Should select highlighted item
- [ ] **Press Escape**: Should close modal

### Screen Reader Tests

#### 1. Semantic Structure
- [ ] **Use screen reader** (NVDA, JAWS, or VoiceOver)
- [ ] **Navigate by headings**: Should announce main heading
- [ ] **Navigate by landmarks**: Should find main, sections
- [ ] **Check page title**: Should announce page purpose

#### 2. Interactive Elements
- [ ] **Tab to chat input**: Should announce "Chat message input, Type your message here..."
- [ ] **Tab to VS Code button**: Should announce "Open VS Code editor, button"
- [ ] **Tab to scroll button**: Should announce "Scroll to bottom of chat, button"

#### 3. Dynamic Content
- [ ] **Send a message**: Status should be announced
- [ ] **Receive response**: New content should be announced
- [ ] **Chat messages**: Should be readable with proper context

#### 4. Modal Content
- [ ] **Open command palette**: Should announce dialog role
- [ ] **Navigate search results**: Should announce options with context
- [ ] **Commands vs Chat items**: Should distinguish between types

### ARIA Compliance Tests

#### 1. Required ARIA Attributes
- [ ] **Chat input**: Has `aria-label` with instructions
- [ ] **VS Code button**: Has `aria-label` describing action
- [ ] **Scroll button**: Has `aria-label` explaining function
- [ ] **Modal**: Has `aria-modal="true"` and `aria-label`

#### 2. Live Regions
- [ ] **Send message**: Status updates announced
- [ ] **Chat responses**: New content announced automatically
- [ ] **Error states**: Errors announced to screen reader

#### 3. Semantic Roles
- [ ] **Main area**: Has `role="main"`
- [ ] **Chat messages**: Have `role="article"`
- [ ] **Status messages**: Have `role="status"`
- [ ] **Search results**: Have `role="listbox"` and `role="option"`

### Focus Management Tests

#### 1. Initial Focus
- [ ] **Page load**: Chat input should be focused
- [ ] **New chat**: Focus should return to input
- [ ] **Modal close**: Focus should return to trigger element

#### 2. Modal Focus Trapping
- [ ] **Open command palette**: Focus should move to search input
- [ ] **Tab within modal**: Should cycle through modal elements only
- [ ] **Close modal**: Focus should return to page

#### 3. Visual Focus Indicators
- [ ] **Tab through elements**: Blue outline should be visible
- [ ] **High contrast mode**: Focus should be more visible
- [ ] **Chat input focus**: Should show blue outline

### Error Handling & Feedback

#### 1. Form Validation
- [ ] **Empty message**: Should handle gracefully (opens VS Code)
- [ ] **Connection errors**: Should not expose technical details
- [ ] **Loading states**: Should be announced to screen readers

#### 2. Status Updates
- [ ] **Message sending**: Status should be announced
- [ ] **Response generating**: Progress should be indicated
- [ ] **Completion**: Success should be communicated

### Mobile & Touch Accessibility

#### 1. Touch Targets
- [ ] **Button sizes**: Should be at least 44x44px
- [ ] **Tap areas**: Should be adequate for touch interaction
- [ ] **Spacing**: Should prevent accidental activation

#### 2. Mobile Screen Readers
- [ ] **VoiceOver (iOS)**: Test with swipe navigation
- [ ] **TalkBack (Android)**: Test with gesture navigation

### Browser-Specific Tests

#### 1. Cross-Browser Testing
- [ ] **Chrome**: Test keyboard navigation and screen reader
- [ ] **Firefox**: Test ARIA support and focus management
- [ ] **Safari**: Test VoiceOver integration
- [ ] **Edge**: Test Windows screen reader compatibility

#### 2. Browser Tools
- [ ] **Chrome DevTools**: Run Lighthouse accessibility audit
- [ ] **Firefox Accessibility Inspector**: Check ARIA tree
- [ ] **axe DevTools**: Scan for violations

## Automated Testing

### Running Tests
```bash
# Install dependencies
npm install

# Run accessibility tests
npm test accessibility.test.tsx

# Run with coverage
npm test -- --coverage accessibility.test.tsx
```

### Lighthouse Audit
```bash
# Install Lighthouse CLI
npm install -g lighthouse

# Run accessibility audit
lighthouse http://localhost:3000/app --only-categories=accessibility
```

### axe-core Testing
```bash
# Install axe CLI
npm install -g @axe-core/cli

# Test specific page
axe http://localhost:3000/app
```

## Expected Results

### ✅ PASS Criteria

#### Keyboard Navigation
- All interactive elements reachable with Tab
- Enter/Space activate buttons correctly
- Focus indicators clearly visible
- Tab opens command palette
- Arrow keys navigate modal results

#### Screen Reader
- All text content readable
- Interactive elements properly labeled
- Dynamic updates announced
- Semantic structure navigable
- No accessibility error announcements

#### ARIA Compliance
- All interactive elements have labels
- Live regions work correctly
- Roles assigned appropriately
- Modal attributes present
- Focus management working

### ❌ FAIL Indicators
- Elements unreachable by keyboard
- Missing or incorrect ARIA labels
- Focus not visible or trapped
- Screen reader cannot navigate
- Dynamic content not announced
- Technical errors exposed to users

## Common Issues & Solutions

### Issue: Focus Not Visible
**Solution**: Check CSS focus-visible styles are applied

### Issue: Screen Reader Not Announcing Updates
**Solution**: Verify aria-live regions are properly implemented

### Issue: Modal Focus Not Trapped  
**Solution**: Ensure modal library handles focus trapping

### Issue: Button Not Activating with Keyboard
**Solution**: Check onKeyDown handlers for Enter/Space keys

## Accessibility Resources

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)
- [WebAIM Screen Reader Testing](https://webaim.org/articles/screenreader_testing/)
- [Chrome DevTools Accessibility](https://developer.chrome.com/docs/devtools/accessibility/)