import { Alert, Avatar, Button, Card, Form, Radio } from 'antd';
import { ArrowRight, Link2 } from 'lucide-react';
import { sessionStore, demoUsers } from '@/entities/session';
import './auth-by-demo.scss';

export function DemoLoginForm({ returningToInsight }: { returningToInsight: boolean }) {
  return <section className="login-section" aria-labelledby="login-heading">
    <Card className="login-card" classNames={{ body: 'login-card-body' }}>
      <h1 id="login-heading">Войти в Альфа-Бизнес</h1>
      <p className="login-description">Выберите пользователя, чтобы продолжить.</p>
      {returningToInsight && <Alert className="shared-login-note" type="info" showIcon
        icon={<Link2 size={18} aria-hidden="true" />}
        title="Вам отправили инсайт. После входа откроется именно этот разбор." />}
      <Form<{ userId: string }> name="demo-login" layout="vertical" requiredMark={false}
        initialValues={{ userId: demoUsers[0].id }} onFinish={({ userId }) => sessionStore.login(userId)}>
        <Form.Item name="userId" label="Пользователь" className="demo-user-field"
          rules={[{ required: true, message: 'Выберите пользователя' }]}>
          <Radio.Group name="demo-user" className="demo-users" aria-label="Пользователь">
            {demoUsers.map((user) => <Radio key={user.id} value={user.id} className="demo-user">
              <span className="demo-user-content">
                <Avatar shape="square" size={34}>{user.initials}</Avatar>
                <span><strong>{user.name}</strong><small>{user.role} · ГК «Северстрой»</small></span>
              </span>
            </Radio>)}
          </Radio.Group>
        </Form.Item>
        <Button type="primary" htmlType="submit" block icon={<ArrowRight size={17} aria-hidden="true" />} iconPlacement="end">Войти</Button>
      </Form>
    </Card>
  </section>;
}
